from odoo import models, fields, api, _
from odoo.exceptions import UserError
import json
import ast


class ResPartner(models.Model):
    _inherit = "res.partner"

    latitude = fields.Float(string="Latitude")
    longitude = fields.Float(string="Longitude")
    pluscode = fields.Char(string="Plus Code")

    ceretax_last_validation = fields.Text(
        string="CereTax Address Result", readonly=True)

    ceretax_address_needs_update = fields.Boolean(
        compute="_compute_ceretax_address_needs_update",
        store=False
    )

    def action_ceretax_validate_address(self):
        self.ensure_one()
        api = self.env["ceretax.api.mixin"]

        result = api.validate_address(self)
        self.ceretax_last_validation = str(result)

        if not result or "error" in result:
               
            raise UserError(_("CereTax validation failed: %s") %
                            result.get("error", "Unknown error"))

        address = result.get("validatedAddress") or {}
        if address:
            vals = {
                "street": address.get("addressLine1") or self.street,
                "street2": address.get("addressLine2") or self.street2,
                "city": address.get("city") or self.city,
                "zip": address.get("postalCode") or self.zip,
                 "latitude": address.get("latitude") or self.latitude,
                  "longitude": address.get("longitude") or self.longitude,
            }

            state_code = address.get("state")
            if state_code:
                state = self.env["res.country.state"].search([
                    ("code", "=", state_code),
                    ("country_id.code", "=", address.get("country"))
                ], limit=1)
                if state:
                    vals["state_id"] = state.id

            country_code = address.get("country")
            if country_code:
                country = self.env["res.country"].search(
                    [("code", "=", country_code)], limit=1)
                if country:
                    vals["country_id"] = country.id

            self.write(vals)
            self.ceretax_last_validation = "Address successfully validated."
        return [
            {
                "type": "ir.actions.client",
                "tag": "display_notification",
                "params": {
                    "title": _("CereTax Address Validation"),
                    "message": _("Address successfully validated and updated.") if address else _("Validation completed."),
                    "type": "success" if address else "warning",
                },
            },
            {
                "type": "ir.actions.client",
                "tag": "reload",
            },
        ]

    def _compute_ceretax_address_needs_update(self):
        mixin = self.env["ceretax.api.mixin"]

        for rec in self:
            raw = rec.ceretax_last_validation

            if not raw:
                rec.ceretax_address_needs_update = False
                continue

            data = None

            # First try JSON
            try:
                data = json.loads(raw)
            except Exception:
                pass

            # If JSON fails, try Python dict string
            if data is None:
                try:
                    data = ast.literal_eval(raw)
                except Exception:
                    rec.ceretax_address_needs_update = False
                    continue

            # Now 'data' is guaranteed to be a proper dict
            rec.ceretax_address_needs_update = mixin._check_validated_address_diff(
                rec, data
            )

    def action_apply_validated_address(self):
        self.ensure_one()
        mixin = self.env["ceretax.api.mixin"]

        data = self._safe_load_ceretax(self.ceretax_last_validation)

        mixin.apply_validated_address(self, data)

        # refresh button state
        self._compute_ceretax_address_needs_update()


    def _safe_load_ceretax(self, raw):
        if not raw:
            return {}

        raw = raw.strip()

        # Remove outer double quotes if wrapped like:  "{'results': ...}"
        if (raw.startswith('"') and raw.endswith('"')) or (raw.startswith("'") and raw.endswith("'")):
            raw = raw[1:-1].strip()

        # 1️⃣ Try valid JSON
        try:
            return json.loads(raw)
        except Exception:
            pass

        # 2️⃣ Fix JSON by replacing single quotes → double quotes
        try:
            fixed = raw.replace("'", '"')
            return json.loads(fixed)
        except Exception:
            pass

        # 3️⃣ Try Python literal (last resort)
        try:
            return ast.literal_eval(raw)
        except Exception:
            return {}
