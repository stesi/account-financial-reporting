# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).

from odoo.exceptions import AccessError
from odoo.tests import new_test_user, tagged

from odoo.addons.account.tests.common import AccountTestInvoicingCommon

PERIOD = {"date_from": "2026-01-01", "date_to": "2026-12-31"}
WIZARDS = {
    "trial.balance.report.wizard": PERIOD,
    "general.ledger.report.wizard": PERIOD,
    "journal.ledger.report.wizard": PERIOD,
    "open.items.report.wizard": {},
    "aged.partner.balance.report.wizard": {},
    "vat.report.wizard": PERIOD,
}


@tagged("post_install", "-at_install")
class TestWizardRestrictions(AccountTestInvoicingCommon):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.company_data["company"]
        cls.unaffected_accounts = cls.env["account.account"].search(
            [
                ("account_type", "=", "equity_unaffected"),
                ("company_ids", "in", cls.company.ids),
            ]
        )

    def _new_wizard(self, model):
        return self.env[model].with_company(self.company).create(dict(WIZARDS[model]))

    def test_single_unaffected_earnings_account(self):
        """One unaffected earnings account: the reports are enabled."""
        self.assertEqual(len(self.unaffected_accounts), 1)
        for model in ("trial.balance.report.wizard", "general.ledger.report.wizard"):
            wizard = self._new_wizard(model)
            self.assertTrue(wizard.only_one_unaffected_earnings_account, model)

    def test_two_unaffected_earnings_accounts(self):
        """Two unaffected earnings accounts in the company: the wizards of the
        trial balance and of the general ledger hide their buttons and show
        the 'only one unaffected earnings account' warning, as in 19.0."""
        self.env["account.account"].create(
            {
                "code": "AFR999",
                "name": "Second unaffected earnings",
                "account_type": "equity_unaffected",
                "company_ids": [(6, 0, self.company.ids)],
            }
        )
        for model in ("trial.balance.report.wizard", "general.ledger.report.wizard"):
            wizard = self._new_wizard(model)
            self.assertFalse(wizard.only_one_unaffected_earnings_account, model)
            wizard.onchange_company_id()
            self.assertFalse(wizard.only_one_unaffected_earnings_account, model)

    def test_invoice_only_user_cannot_use_reports(self):
        """A user with Invoicing only (no accounting read access) cannot
        create the report wizards; an accountant can."""
        invoice_user = new_test_user(
            self.env,
            login="afr_invoice_only",
            groups="account.group_account_invoice",
            company_id=self.company.id,
            company_ids=[(6, 0, self.company.ids)],
        )
        self.assertFalse(invoice_user.has_group("account.group_account_readonly"))
        accountant = new_test_user(
            self.env,
            login="afr_accountant",
            groups="account.group_account_user",
            company_id=self.company.id,
            company_ids=[(6, 0, self.company.ids)],
        )
        for model, vals in WIZARDS.items():
            with self.assertRaises(AccessError, msg=model):
                self.env[model].with_user(invoice_user).create(dict(vals))
            wizard = self.env[model].with_user(accountant).create(dict(vals))
            self.assertTrue(wizard, model)
        config = self.env["account.age.report.configuration"]
        with self.assertRaises(AccessError):
            config.with_user(invoice_user).search([])
        config.with_user(accountant).search([])
