from odoo import models, fields, _
from .ceretax_document_mixin import CeretaxDocumentMixin
import json
from odoo.exceptions import UserError
import requests


class AccountMove(models.Model, CeretaxDocumentMixin):
    _inherit = 'account.move'
    ceretax_last_address_validation = fields.Text(
        string="CereTax Address Validation Result",
        readonly=True
    )

    ceretax_transaction_id = fields.Char()
    ceretax_tax_amount = fields.Monetary(currency_field="currency_id")
    ceretax_status = fields.Char()
    ceretax_last_error = fields.Text()
    ceretax_response = fields.Text()

    def _ceretax_get_lines(self):
        return self.invoice_line_ids

    def _ceretax_get_partner(self):
        return self.partner_id

    def _ceretax_get_document_name(self):
        return self.name or self.ref

    def _ceretax_get_document_total(self):
        return self.amount_untaxed

    def _ceretax_get_document_date(self):
        return fields.Date.to_string(self.invoice_date or fields.Date.today())

    def action_custom_button(self):
        return self.amount_total

    def action_ceretax_validate_so_address(self):
        api = self.env["ceretax.api.mixin"]

        for record in self:
            # Detect context by model
            if record._name == "res.partner":
                partner = record
                target_order = None
            elif record._name == "sale.order":
                partner = record.partner_shipping_id or record.partner_id
                target_order = record
            elif record._name == "account.move":
                partner = record.partner_shipping_id or record.partner_id
                target_order = record
            else:
                continue  # ignore other models

            result = api.validate_address(partner)

            # Store raw result for audit
            if target_order:
                target_order.ceretax_last_address_validation = json.dumps(
                    result)
            else:
                partner.ceretax_last_address_validation = json.dumps(result)

            validated = result.get("validatedAddress") or {}
            if not validated:
                return {
                    "type": "ir.actions.client",
                    "tag": "display_notification",
                    "params": {
                        "title": _("CereTax Address Validation"),
                        "message": _("Validation completed (no corrections received)."),
                        "type": "warning",
                    },
                }

            # Build partner update dict safely
            partner_vals = {}
            if validated.get("addressLine1"):
                partner_vals["street"] = validated["addressLine1"]
            if validated.get("addressLine2"):
                partner_vals["street2"] = validated["addressLine2"]
            if validated.get("city"):
                partner_vals["city"] = validated["city"]
            if validated.get("postalCode"):
                partner_vals["zip"] = validated["postalCode"]

            # State update
            state_code = validated.get("state")
            if state_code:
                state = self.env["res.country.state"].search([
                    ("code", "=", state_code),
                    ("country_id.code", "=", validated.get("country")),
                ], limit=1)
                if state:
                    partner_vals["state_id"] = state.id

            # Country update
            country_code = validated.get("country")
            if country_code:
                country = self.env["res.country"].search(
                    [("code", "=", country_code)], limit=1)
                if country:
                    partner_vals["country_id"] = country.id

            if partner_vals:
                partner.write(partner_vals)

                # Post chatter message depending on context
                if target_order:
                    target_order.message_post(
                        body=_("Shipping address successfully validated and updated."))
                else:
                    partner.message_post(
                        body=_("Partner address successfully validated and updated."))

        return [
            {
                "type": "ir.actions.client",
                "tag": "display_notification",
                "params": {
                    "title": _("CereTax Address Validation"),
                    "message": _("Address successfully validated and updated."),
                    "type": "success",
                },
            },
            {
                "type": "ir.actions.client",
                "tag": "reload",
            },
        ]

    def _ceretax_auto_status_update(self):
        for move in self:
            invoice_number = move.name
            ceretax_tx = self.env["ceretax.transaction"].sudo().search(
                [], limit=1000)
            matched_tx = False
            tx_data = None
            for tx in ceretax_tx:
                try:
                    body = json.loads(tx.response_body or "{}")
                except:
                    continue

                inv = body.get("invoice", {})
                if inv.get("invoiceNumber") == invoice_number:
                    tx_data = body
                    matched_tx = True
                    break
            if not matched_tx or not tx_data:
                raise UserError(
                    f"No matching CereTax transaction found for invoice {invoice_number}. Click Ceretax Tax to get Tax.")

            ksuid = tx_data.get("ksuid")
            system_num = tx_data.get("systemTraceAuditNumber")
            status = "Suspended"
            # tx_data.get("status", {}).get("currentStatus", "Suspended")

            if not ksuid:
                raise UserError("CereTax transaction missing ksuid")

            if not system_num:
                raise UserError(
                    "CereTax transaction missing systemTraceAuditNumber")

            payload = {
                "ksuid": ksuid,
                "systemTraceAuditNumber": system_num,
                "transactionStatus": status
            }

            token = self.env['ir.config_parameter'].sudo(
            ).get_param("ceretax.api_key")
            if not token:
                raise UserError("Missing CereTax API Key in System Parameters")

            headers = {
                "accept": "application/json",
                "content-type": "application/json",
                "x-api-key": f"{token}",
            }

            url = "https://calc.cert.ceretax.net/status"

            try:
                response = requests.post(
                    url, json=payload, headers=headers, timeout=40)
                response.raise_for_status()
            except Exception as e:
                raise UserError(f"CereTax Status API Failed:\n{e}")

            result = response.json()

            # move.ceretax_status = result.get("transactionStatus")

            return result

    # def action_post(self):
    #     res = super().action_post()
    #     self._ceretax_auto_status_update()
    #     return res

    # def button_draft(self):
    #     res = super().button_draft()
    #     self._ceretax_auto_status_update()
    #     return res
    def action_post(self):
        # Always allow posting
        res = super().action_post()

        # Trigger CereTax AFTER posting, non-blocking
        for move in self:
            if move.move_type in ("out_invoice", "out_refund"):

                # Check if CereTax is enabled
                if self.env['ir.config_parameter'].sudo().get_param("ceretax.enable"):

                    try:
                        move._ceretax_auto_status_update()
                    except Exception as e:
                        # Do NOT block posting — only log message
                        move.message_post(
                            body=f"<b>CereTax Auto Update Failed:</b><br/>{str(e)}"
                        )

        return res

    def button_draft(self):
        # Always allow reset to draft
        res = super().button_draft()

        for move in self:
            # Only invoices / credit notes
            if move.move_type in ("out_invoice", "out_refund"):

                # Check if CereTax is enabled
                if self.env['ir.config_parameter'].sudo().get_param("ceretax.enable"):

                    try:
                        move._ceretax_auto_status_update()
                    except Exception as e:
                        # Log in chatter, do NOT block draft action
                        move.message_post(
                            body=f"<b>CereTax Auto Update Failed (Draft Reset):</b><br/>{str(e)}"
                        )

        return res


class AccountMoveLine(models.Model):
    _inherit = 'account.move.line'

    ceretax_line_tax = fields.Monetary(
        currency_field="currency_id", string="CereTax Line Tax")
    ceretax_tax_details = fields.Text(string="CereTax Tax Details")
    ceretax_line_id = fields.Char(string="CereTax Line ID")
