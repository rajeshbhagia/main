from odoo import models, fields, _
from odoo.exceptions import UserError
import json


class SaleOrder(models.Model):
    _inherit = "sale.order"

    ceretax_last_address_validation = fields.Text(
        string="CereTax Address Validation Result",
        readonly=True
    )

    def _get_delivery_amount_safe(self):
        """Return shipping amount if delivery module installed else 0."""
        if "amount_delivery" in self._fields:
            return self.amount_delivery or 0.0
        return 0.0

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
                        "title": _("CereTax Address Validation "),
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
                    # if address else _("Validation completed."),
                    "type": "success",
                    # if address else "warning",
                },
            },
            {
                "type": "ir.actions.client",
                "tag": "reload",
            },
        ]
