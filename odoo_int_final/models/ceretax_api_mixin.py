
from odoo import models, _, fields
from odoo.exceptions import UserError
import requests
import json
import logging


ENVIRONMENTS = {
    "cert": {"transaction_base": "https://calc.cert.ceretax.net"},
    "prod": {"transaction_base": "https://calc.prod.ceretax.net"}
}


class CeretaxApiMixin(models.AbstractModel):
    _name = "ceretax.api.mixin"
    _description = "CereTax API Helper"
    _logger = logging.getLogger(__name__)

    def _conf(self):
        """Fetch CereTax configuration with safe and flexible parsing."""
        icp = self.env['ir.config_parameter'].sudo()

        def get_bool(key, default=False):
            """Support True, true, 1, yes"""
            val = icp.get_param(key, default)
            return str(val).strip().lower() in ("true", "1", "yes")

        # Read params using your PARAM mapping
        env = icp.get_param("odoo_ceretax.environment", "cert")
        api_key = icp.get_param("odoo_ceretax.api_key", "")
        enabled = icp.get_param("odoo_ceretax.enable_ceretax", False)
        logging = icp.get_param("odoo_ceretax.enable_logging", False)
        # get_bool("odoo_ceretax.enable", False)

        # Unknown environment fallback
        base_url = ENVIRONMENTS.get(env, ENVIRONMENTS["cert"])[
            "transaction_base"]

        return {
            "enabled": enabled,
            "api_key": api_key,
            "environment": env,
            "base": base_url,
            "logging": logging
        }

    def _ceretax_request(self, method, path, payload=None, sale_order=None, sale_line=None):
        cfg = self._conf()
        settings = self.env['res.config.settings'].sudo().get_values()
        logging_enabled = settings.get("enable_logging")
        if not cfg["enabled"]:
            raise UserError(
                _("CereTax is disabled in the configuration settings."))

        if not cfg["api_key"]:
            raise UserError(
                _("CereTax API Key is missing. Configure it in settings."))

        url = f"{cfg['base']}/{path}"
        headers = {
            "x-api-key": cfg["api_key"],
            "Content-Type": "application/json"
        }
        data = json.dumps(payload) if payload else None

        try:
            resp = requests.request(
                method.upper(),
                url,
                headers=headers,
                data=data,
                timeout=30
            )
        except Exception as e:
            raise UserError(_("Failed to connect to CereTax: %s") % e)

        # Correctly link the log to the order + line
        log_vals = {
            "name": f"CereTax Request - {fields.Datetime.now()}",
            "endpoint": url,
            "request_headers": json.dumps(headers),
            "request_body": data or "",
            "status_code": resp.status_code,
            "response_body": resp.text,
        }

        if sale_order:
            log_vals["sale_order_id"] = sale_order.id

        if sale_line:
            log_vals["sale_line_id"] = sale_line.id

        if logging_enabled:
            self.env["ceretax.transaction"].sudo().create(log_vals)

        if resp.status_code >= 400:
            raise UserError(
                _("CereTax API Error %s:\n%s") % (resp.status_code, resp.text)
            )

        return resp

    def validate_address(self, partner):
        """
        Correct implementation using CereTax Address Validation API.
        GET request with query params.
        """

        settings = self.env['res.config.settings'].sudo().get_values()
        api_key = settings.get("api_key")
        ceretax_enabled = settings.get("enable_ceretax")
        ceretax_enabled_logging = settings.get("enable_logging")
        ceretax_addressvalidation = settings.get("enable_addressvalidation")

        if not ceretax_enabled:
            raise UserError(
                _("CereTax is disabled in the configuration settings."))

        if not ceretax_addressvalidation:
            raise UserError(
                _("CereTax Address Validation is disabled in the configuration settings."))

        if not api_key:
            raise UserError(_("CereTax API key not configured."))

        base_url = "https://av.cert.ceretax.net/validate"

        if not partner.street or not partner.city or not partner.state_id.code or not partner.zip:
            raise UserError(_(
                "No address found or incomplete address. "
                "Please provide Line 1, City, State, and Postal Code."))

        params = {
            "addressLine1": partner.street or "",
            "addressLine2": partner.street2 or "",
            "city": partner.city or "",
            "state": partner.state_id.code or "",
            "postalCode": partner.zip or "",
            "country": partner.country_id.code or "US",
            "latitude": partner.latitude or "0.0",
            "longitude": partner.longitude or "0.0",

        }

        headers = {
            "x-api-key": api_key,
            "accept": "application/json",
        }

        try:
            response = requests.get(
                base_url, headers=headers, params=params, timeout=20)
        except Exception as e:
            raise UserError(_("CereTax Address Validation failed: %s") % e)

        if response.status_code not in (200, 201):
            raise UserError(_("CereTax returned error (%s): %s") %
                            (response.status_code, response.text))

        data = response.json()

        if ceretax_enabled_logging:
            # Log transaction
            self.env["ceretax.transaction"].create({
                "name": "Address Validation",
                "request_payload": json.dumps(params),
                "response_payload": json.dumps(data),
                "status": "success",
            })

        # Save result to partner field
        partner.write({
            # store nicely formatted JSON
            "ceretax_last_validation": json.dumps(data, indent=2)
        })

        return data

    def apply_validated_address(self, record, ceretax_result):
        """
        Generic method to update Odoo address fields using
        CereTax validatedAddressDetails.
        Works for res.partner, sale.order, or any other model.
        """

        if not record:
            return False

        if (
            not ceretax_result
            or "results" not in ceretax_result
            or not ceretax_result["results"]
        ):
            return False

        res = ceretax_result["results"][0]

        submitted = res.get("submittedAddressDetails", {}) or {}
        validated = res.get("validatedAddressDetails", {}) or {}
        location = res.get("location", {}) or {}

        changes = {}
        debug = []

        def norm(v):
            if not v:
                return ""
            return str(v).strip().upper()

        # Field map for simple string fields
        field_map = {
            "street": "addressLine1",
            "street2": "addressLine2",
            "city": "city",
            "zip": "postalCode",
        }

        # ==========================================
        # COUNTRY
        # ==========================================
        if validated.get("country"):
            country = self.env["res.country"].search(
                [("code", "=", validated["country"])], limit=1
            )
            if country:
                if norm(submitted.get("country")) != norm(validated.get("country")):
                    changes["country_id"] = country.id
                    debug.append(
                        f"Country: {submitted.get('country')} → {validated.get('country')}")

        # ==========================================
        # STATE
        # ==========================================
        if validated.get("state"):
            state = self.env["res.country.state"].search(
                [("code", "=", validated["state"])], limit=1
            )
            if state:
                if norm(submitted.get("state")) != norm(validated.get("state")):
                    changes["state_id"] = state.id
                    debug.append(
                        f"State: {submitted.get('state')} → {validated.get('state')}")

        # ==========================================
        # STRING FIELDS (street, street2, city, zip)
        # ==========================================
        for odoo_field, api_field in field_map.items():
            sub_val = norm(submitted.get(api_field))
            val_val = norm(validated.get(api_field))

            if sub_val != val_val:
                changes[odoo_field] = validated.get(api_field)
                debug.append(
                    f"{odoo_field}: {submitted.get(api_field)} → {validated.get(api_field)}")

        # ==========================================
        # ZIP+4
        # ==========================================
        if validated.get("postalCode") and validated.get("plus4"):
            full_zip = f"{validated.get('postalCode')}-{validated.get('plus4')}"
            if norm(submitted.get("postalCode")) != norm(full_zip):
                changes["zip"] = full_zip
                debug.append(
                    f"ZIP+4: {submitted.get('postalCode')} → {full_zip}")

        # Extract location data safely

        validated_lat = location.get("latitude")
        validated_lng = location.get("longitude")
        validated_plus_code = location.get("plusCode")

        # Compare Latitude
        if validated_lat is not None:
            if norm(record.latitude) != norm(validated_lat):
                changes["latitude"] = validated_lat
                debug.append(f"Latitude: {record.latitude} → {validated_lat}")

        # Compare Longitude
        if validated_lng is not None:
            if norm(record.longitude) != norm(validated_lng):
                changes["longitude"] = validated_lng
                debug.append(
                    f"Longitude: {record.longitude} → {validated_lng}")

        # Compare Plus Code
        if validated_plus_code:
            if norm(getattr(record, "pluscode", "")) != norm(validated_plus_code):
                changes["pluscode"] = validated_plus_code
                debug.append(
                    f"Plus Code: {getattr(record, 'pluscode', None)} → {validated_plus_code}")

        # ==========================================
        # APPLY CHANGES
        # ==========================================
        if changes:
            record.write(changes)
            self._logger.info("CereTax Address Updated:\n" + "\n".join(debug))
            return True

        return False

    def _check_validated_address_diff(self, record, ceretax_result):
        """
        Returns True if validated address or location differs from the record's stored values.
        This uses comparison logic only (NO writing).
        """

        if not record:
            return False

        if (
            not ceretax_result
            or "results" not in ceretax_result
            or not ceretax_result["results"]
        ):
            return False

        res = ceretax_result["results"][0]

        submitted = res.get("submittedAddressDetails", {}) or {}
        validated = res.get("validatedAddressDetails", {}) or {}
        location = res.get("location", {}) or {}

        def norm(v):
            return ("" if v is None else str(v)).strip().upper()

        # ===========================
        # ZIP + 4 handling
        # ===========================
        validated_zip = ""
        if validated.get("postalCode"):
            validated_zip = validated.get("postalCode")
            if validated.get("plus4"):
                validated_zip = f"{validated_zip}-{validated['plus4']}"

        # ===========================
        # Build current Odoo Address
        # ===========================
        current = {
            "addressLine1": record.street or "",
            "addressLine2": record.street2 or "",
            "city": record.city or "",
            "state": record.state_id.code or "",
            "postalCode": record.zip or "",
            "country": record.country_id.code or "",
            "latitude": record.latitude or 0.0,
            "longitude": record.longitude or 0.0,
            "plusCode": record.pluscode or "",
        }

        # ===========================
        # Compare Address Fields
        # ===========================
        compare_fields = [
            "addressLine1",
            "addressLine2",
            "city",
            "state",
            "country",
        ]

        for f in compare_fields:
            if norm(current[f]) != norm(validated.get(f, "")):
                return True

        # ===========================
        # Compare ZIP / ZIP+4
        # ===========================
        if norm(current["postalCode"]) != norm(validated_zip):
            return True

        # ===========================
        # Compare Location (Lat / Long / Plus Code)
        # ===========================
        if "latitude" in location:
            if float(current["latitude"]) != float(location.get("latitude", 0.0)):
                return True

        if "longitude" in location:
            if float(current["longitude"]) != float(location.get("longitude", 0.0)):
                return True

        if "plusCode" in location:
            if norm(current["plusCode"]) != norm(location.get("plusCode", "")):
                return True

        return False

    def _get_invoice_profile(self):
        icp = self.env['ir.config_parameter'].sudo()
        return {
            "business_type": icp.get_param("ceretax.business_type", "01"),
            "customer_type": icp.get_param("ceretax.customer_type", "01"),
            "unit_type": icp.get_param("ceretax.unit_type", "01"),
            "seller_type": icp.get_param("ceretax.seller_type", "01"),
            "profileId": icp.get_param("ceretax.profile", "sales"),
        }

    def ceretax_status_from_state(self, state):
        # state = order.state

        if state in ("draft", "sent", "sale", "done"):
            return "Quote"

        if state in ("posted"):
            return "Posted"

        if state == "cancel":
            return "Suspended"

        return "Active"
