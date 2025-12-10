# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import UserError
import requests, json


ENVIRONMENTS = {
    "cert":{"transaction_base":"https://calc.cert.ceretax.net"},
    "prod":{"transaction_base":"https://calc.prod.ceretax.net"}
}

PARAM = {
    "api_key": "odoo_ceretax.api_key",
    "environment": "odoo_ceretax.environment",
    "profile": "odoo_ceretax.profile",
    "enable_ceretax": "odoo_ceretax.enable_ceretax",
    "post_finalized": "odoo_ceretax.post_finalized",
    "enable_logging": "odoo_ceretax.enable_logging",
    "enable_addressvalidation": "odoo_ceretax.enable_addressvalidation",
    "validate_customer_address": "odoo_ceretax.validate_customer_address",
    "validate_every_transaction": "odoo_ceretax.validate_every_transaction",
    "business_type": "odoo_ceretax.business_type",
    "customer_type": "odoo_ceretax.customer_type",
    "seller_type": "odoo_ceretax.seller_type",
    "unit_type": "odoo_ceretax.unit_type",
    "ps_code": "odoo_ceretax.ps_code",
    "tax_included": "odoo_ceretax.tax_included",
}


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    api_key = fields.Char(string="API Key", config_parameter="ceretax.api_key", password = True)

    environment = fields.Selection([
        ('cert', 'Sandbox'),
        ('prod', 'Production')
    ], string="Environment", config_parameter="ceretax.environment", default="cert")
    
    profile = fields.Char(string="Profile", config_parameter="ceretax.profile")


    enable_ceretax = fields.Boolean(string="Enable CereTax", config_parameter="ceretax.enable")
    enable_addressvalidation = fields.Boolean(string="Enable Address Validation", config_parameter="ceretax.addressvalidation")
    post_finalized = fields.Boolean(string="Post Finalized Transactions", config_parameter="ceretax.post_finalized")
    enable_logging = fields.Boolean(string="Enable Logging", config_parameter="ceretax.logging")

    validate_customer_address = fields.Boolean(string="Validate Customer Address", config_parameter="ceretax.validate_customer_address")
    validate_every_transaction = fields.Boolean(string="Validate Every Transaction", config_parameter="ceretax.validate_every_transaction")

    business_type = fields.Selection(
        selection=lambda self: self._get_business_types(),
        string="Business Type",
        config_parameter="ceretax.business_type"
    )

    # customer_type = fields.Char(string="Customer Type", config_parameter="ceretax.customer_type")
    customer_type = fields.Selection(
        selection=lambda self: self._get_customer_types(),
        string="Customer Type",
        config_parameter="ceretax.customer_type"
    )   
   
    # ps_code = fields.Char(string="PS Code", config_parameter="ceretax.ps_code")
    ceretax_ps_code_id = fields.Many2one(
        'ceretax.ps.code',
        string="Default PS Code",
        config_parameter='ceretax.default_ps_code'
    )
    ps_code = fields.Char(
        related="ceretax_ps_code_id.ps_code",
        store=True,
        readonly=True,
    )

    unit_type = fields.Selection(
        selection=lambda self: self._get_unit_types(),
        string="Unit Types",
        config_parameter="ceretax.unit_type"
    )

    seller_type = fields.Selection(
        selection=lambda self: self._get_seller_types(),
        string="Seller Type",
        config_parameter="ceretax.seller_type"
    )   

    tax_included = fields.Boolean(string="Tax Included", config_parameter="ceretax.tax_included")

    about_ceretax = fields.Char(string="About CereTax URL", config_parameter="ceretax.about_url")

    def get_values(self):
        """Load values from ir.config_parameter"""
        res = super().get_values()
        icp = self.env["ir.config_parameter"].sudo()
        res.update(
            api_key=icp.get_param(PARAM["api_key"], default=""),
            environment=icp.get_param(PARAM["environment"], default="cert"),
            profile=icp.get_param(PARAM["profile"], default=""),
            enable_ceretax=icp.get_param(PARAM["enable_ceretax"], default="False") == "True",
            enable_addressvalidation=icp.get_param(PARAM["enable_addressvalidation"], default="False") == "True",
            post_finalized=icp.get_param(PARAM["post_finalized"], default="False") == "True",
            enable_logging=icp.get_param(PARAM["enable_logging"], default="False") == "True",
            validate_customer_address=icp.get_param(PARAM["validate_customer_address"], default="False") == "True",
            validate_every_transaction=icp.get_param(PARAM["validate_every_transaction"], default="False") == "True",
            business_type=icp.get_param(PARAM["business_type"], default=""),
            customer_type=icp.get_param(PARAM["customer_type"], default=""),
            seller_type=icp.get_param(PARAM["seller_type"], default=""),
            unit_type=icp.get_param(PARAM["unit_type"], default=""),
            ps_code=icp.get_param(PARAM["ps_code"], default=""),
            tax_included=icp.get_param(PARAM["tax_included"], default="False") == "True",
        )
        return res

    def set_values(self):
        """Save values into ir.config_parameter"""
        super().set_values()
        icp = self.env["ir.config_parameter"].sudo()
        icp.set_param(PARAM["api_key"], self.api_key or "")
        icp.set_param(PARAM["environment"], self.environment or "cert")
        icp.set_param(PARAM["profile"], self.profile or "")
        icp.set_param(PARAM["enable_ceretax"], str(bool(self.enable_ceretax)))
        icp.set_param(PARAM["enable_addressvalidation"], str(bool(self.enable_addressvalidation)))
        icp.set_param(PARAM["post_finalized"], str(bool(self.post_finalized)))
        icp.set_param(PARAM["enable_logging"], str(bool(self.enable_logging)))
        icp.set_param(PARAM["validate_customer_address"], str(bool(self.validate_customer_address)))
        icp.set_param(PARAM["validate_every_transaction"], str(bool(self.validate_every_transaction)))
        icp.set_param(PARAM["business_type"], self.business_type or "")
        icp.set_param(PARAM["customer_type"], self.customer_type or "")
        icp.set_param(PARAM["seller_type"], self.seller_type or "")
        icp.set_param(PARAM["unit_type"], self.unit_type or "")
        icp.set_param(PARAM["ps_code"], self.ps_code or "")
        icp.set_param(PARAM["tax_included"], str(bool(self.tax_included)))

    def action_test_connection(self):
        icp = self.env['ir.config_parameter'].sudo()
        env = icp.get_param("ceretax.environment", "cert") 
        if env not in ENVIRONMENTS:
            raise UserError(f"Unknown environment: {env}")

        base = ENVIRONMENTS[env]["transaction_base"]
        url = f"{base}/test"
        key = icp.get_param("ceretax.api_key", "")
        if not key:
            raise UserError("API Key missing")

        resp = requests.post(url, headers={"x-api-key": key})
        self.env["ceretax.transaction"].sudo().create({
            "name": f"Test Connection ({env.upper()})",
            "endpoint": url,
            "request_headers": json.dumps({"x-api-key": key}),
            "status_code": resp.status_code,
            "response_body": resp.text,
        })
        if resp.status_code != 200:
            raise UserError(f"Failed: {resp.text}")
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {"message": "Connection OK", "type": "success"},
        }

    def _get_ps_codes(self):
        icp = self.env['ir.config_parameter'].sudo()
        key = icp.get_param("ceretax.api_key", "")

        url = "https://data.cert.ceretax.net/psCodes"
        headers = {
            "accept": "application/json",
            "x-api-key": key
        }
        try:
            response = requests.get(url, headers=headers, timeout=10)
            response.raise_for_status()
            data = response.json()
            # Build dropdown as (value, label)
            return [
                (c["psCode"], f"{c['psCode']} - {c['psCodeDescription']}")
                for c in data
            ]
        except Exception:
            return []

    def _get_unit_types(self):
        icp = self.env['ir.config_parameter'].sudo()
        key = icp.get_param("ceretax.api_key", "")

        url = "https://data.cert.ceretax.net/unitTypes"
        headers = {
            "accept": "application/json",
            "x-api-key": key
        }
        try:
            response = requests.get(url, headers=headers, timeout=10)
            response.raise_for_status()
            data = response.json()
            # Build dropdown as (value, label)
            return [(c["unitType"], c["unitTypeDescription"]) for c in data]
        except Exception:
            return []

    def _get_business_types(self):
        icp = self.env['ir.config_parameter'].sudo()
        key = icp.get_param("ceretax.api_key", "")

        url = "https://data.cert.ceretax.net/businessTypes"
        headers = {
            "accept": "application/json",
            "x-api-key": key
        }
        try:
            response = requests.get(url, headers=headers, timeout=10)
            response.raise_for_status()
            data = response.json()
            # Build dropdown as (value, label)
            return [(c["businessType"], c["businessTypeDescription"]) for c in data]
        except Exception:
            return []

    def _get_customer_types(self):
            icp = self.env['ir.config_parameter'].sudo()
            key = icp.get_param("ceretax.api_key", "")

            url = "https://data.cert.ceretax.net/customerTypes"
            headers = {
                "accept": "application/json",
                "x-api-key": key
            }
            try:
                response = requests.get(url, headers=headers, timeout=10)
                response.raise_for_status()
                data = response.json()
                # Build dropdown as (value, label)
                return [(c["customerType"], c["customerTypeDescription"]) for c in data]
            except Exception:
                return []

    def _get_seller_types(self):
            icp = self.env['ir.config_parameter'].sudo()
            key = icp.get_param("ceretax.api_key", "")

            url = "https://data.cert.ceretax.net/sellerTypes"
            headers = {
                "accept": "application/json",
                "x-api-key": key
            }
            try:
                response = requests.get(url, headers=headers, timeout=10)
                response.raise_for_status()
                data = response.json()
                # Build dropdown as (value, label)
                return [(c["sellerType"], c["sellerTypeDescription"]) for c in data]
            except Exception:
                return []
