from odoo import models, api, fields, _
from odoo.exceptions import UserError
import json
import logging

_logger = logging.getLogger(__name__)


class CeretaxDocumentMixin(models.AbstractModel):
    _name = "ceretax.document.mixin"
    _description = "Shared logic between Sale Order & Invoice (Account Move)"

    # --------------------------------------------------------------------
    # MUST BE IMPLEMENTED BY MODEL
    # --------------------------------------------------------------------
    def _ceretax_get_lines(self):
        """Return recordset of document lines."""
        raise NotImplementedError

    def _ceretax_get_partner(self):
        """Return shipping/customer partner."""
        raise NotImplementedError

    def _ceretax_get_company_partner(self):
        """Return company partner."""
        return self.company_id.partner_id

    def _ceretax_get_document_name(self):
        raise NotImplementedError

    def _ceretax_get_document_total(self):
        raise NotImplementedError

    def _ceretax_get_document_date(self):
        return fields.Date.to_string(self.date or fields.Date.today())

    # --------------------------------------------------------------------
    # SHARED: BUILD PAYLOAD
    # --------------------------------------------------------------------
    def _build_ceretax_payload(self):
        self.ensure_one()
        icp = self.env['ir.config_parameter'].sudo()
        settings_ps_code = icp.get_param("ceretax.ps_code", "10010100")

        lines = self._ceretax_get_lines()
        partner = self._ceretax_get_partner()
        comp = self._ceretax_get_company_partner()
        document_name = self._ceretax_get_document_name()

        if not lines:
            raise UserError(_('Cannot calculate tax — No line items found.'))

        if not partner:
            raise UserError(_('No customer/shipping address found.'))

        # assign line IDs
        for i, l in enumerate(lines, start=1):
            l.ceretax_line_id = str(i)

        invoice_date = self._ceretax_get_document_date()

        # profile
        try:
            profile = self.env['ceretax.api.mixin']._get_invoice_profile() or {}
        except Exception:
            profile = {'profileId': 'sales', 'business_type': '01', 'customer_type': '01', 'unit_type':'01', 'seller_type':'01'}

        line_items = []

        for line in lines:
            qty = float(self._ceretax_get_line_qty(line))
            ps_code = getattr(line.product_id, 'ceretax_ps_code', None) or  line.product_id.categ_id.ceretax_ps_code_id.ps_code or settings_ps_code
           

            line_items.append({
                'lineId': line.ceretax_line_id,
                'psCode': ps_code,
                'revenue': float(line.price_subtotal or 0.0),
                'units': {'quantity': qty,
                         'type': profile.get('unit_type') if profile else '01'
                         },
                'dateOfTransaction': invoice_date,
                'situs': {
                    'shipFromAddress': {
                        'addressLine1': comp.street or '',
                        'city': comp.city or '',
                        'state': comp.state_id.code or '',
                        'postalCode': comp.zip or '',
                        'country': comp.country_id.code or 'US',
                    },
                    'shipToAddress': {
                        'addressLine1': partner.street or '',
                        'city': partner.city or '',
                        'state': partner.state_id.code or '',
                        'postalCode': partner.zip or '',
                        'country': partner.country_id.code or 'US',
                    },
                },
            })

        payload = {
            'configuration': {
                 'status': self.env['ceretax.api.mixin'].ceretax_status_from_state(self.state),
                'calculationType': 'S',
                 'responseOptions': {'passThroughType': {'excludeOptionalTaxesInTaxOnTax': False}},
                'contentYear': str(fields.Date.today().year),
                'contentMonth': str(fields.Date.today().month),
                 'decimals': 2,
                'profileId': profile.get("profileId", "sales"),
            },
            'invoice': {
                'businessType': profile.get('business_type') if profile else '01',
                'customerType': profile.get('customer_type') if profile else '01',
                'sellerType': profile.get('seller_type') if profile else '01',
                # 'invoiceNumber': if document_name else '',
                'invoiceNumber': document_name or self.name or f"DraftInvoice-{self.id}",
                'invoiceDate': invoice_date,
                'invoiceTotalAmount': float(self._ceretax_get_document_total()),
                'customerAccount': str(partner.id),
                'lineItems': line_items,
            }
        }
        return payload

    # --------------------------------------------------------------------
    # SHARED: APPLY RESPONSE
    # --------------------------------------------------------------------
    def _apply_ceretax_response(self, resp):
        self.ensure_one()
        lines = self._ceretax_get_lines()

        items = (resp.get("invoice") or {}).get("lineItems", [])
        valid_ids = set(lines.mapped("ceretax_line_id"))
        items = [i for i in items if str(i.get("lineId")) in valid_ids]

        for item in items:
            line_id = str(item.get("lineId"))
            line = lines.filtered(lambda l: l.ceretax_line_id == line_id)
            if not line:
                continue

            tax_amount = float(item.get("totalTaxLine") or 0)
            line.ceretax_line_tax = tax_amount
            line.ceretax_tax_details = json.dumps(item)

            taxes = item.get('taxes') or []
            tax_ids = []

            # ----------------------------------------------------
            # Create CereTax tax lines in sale.order.line.tax
            # ----------------------------------------------------
            for t in taxes:
                try:
                    # rate_val = t.get('rate') or 0.0
                    # rate = float(rate_val) * 100 if 0 < rate_val < 1 else float(rate_val)
                    total_tax_val = round(float(t.get('totalTax') or 0.0), 2)

                  # Pick correct tax storage model
                    if line._name == "sale.order.line":
                        TaxModel = self.env["sale.order.line.tax"]
                        fk_name = "sale_line_id"
                    else:
                        TaxModel = self.env["account.move.line.tax"]
                        fk_name = "move_line_id"

                    domain = [
                        (fk_name, '=', line.id),
                        ('description', '=', t.get('description')),
                        ('rate', '=', t.get('rate')),
                        ('total_tax', '=', total_tax_val),
                    ]

                    existing = TaxModel.search(domain, limit=1)

                    values = {
                        fk_name: line.id,
                        'description': t.get('description'),
                        'tax_authority': t.get('taxAuthorityName'),
                        'tax_level': t.get('taxLevelDesc'),
                        'tax_type': t.get('taxTypeDesc'),
                        'tax_class': t.get('taxTypeClassDesc'),
                        'rate': t.get('rate') or 0.0,
                        'calc_base': float(t.get('calculationBaseAmt') or 0.0),
                        'total_tax': float(t.get('totalTax') or 0.0),
                        'taxable': t.get('taxable'),
                        'geocode': t.get('geocode', {}).get('geocode'),
                        'extra': json.dumps(t),
                        'tax_type_ref_desc': t.get('taxTypeRefDesc'),
                        'exempt_amount': t.get('exemptAmount'),
                        'percent_taxable': t.get('percentTaxable'),
                        'non_taxable_amount': t.get('nonTaxableAmount'),
                    }

                    if existing:
                        existing.write(values)
                    else:
                        TaxModel.create(values)

                except Exception as e:
                    _logger.error("Failed creating/updating tax line: %s", e)

            for t in taxes:
                name = t.get('description') or t.get('taxName') or 'CereTax'
                raw_rate = t.get('rate') or t.get('percentage') or 0.0
                try:
                    rate = float(raw_rate)
                except (TypeError, ValueError):
                    rate = 0.0

                if 0 < rate < 1:  # fractional rate like 0.06
                    rate *= 100.0

                rate = round(rate, 4)

                tax = self.env['account.tax'].sudo().search([
                    ('name', '=', name),
                    ('type_tax_use', '=', 'sale')
                ], limit=1)

                if not tax or abs(tax.amount - rate) > 0.0001:
                    # Ensure unique tax name
                    Tax = self.env['account.tax'].sudo()
                    company_id = self.company_id.id

                    # Check all existing taxes with same base name
                    existing = Tax.search([('name', '=', name), ('company_id', '=', company_id)])

                    new_name = name

                    if existing:
                        # Find all taxes whose name starts with original name
                        similar = Tax.search([
                            ('name', 'ilike', f"{name}%"),
                            ('company_id', '=', company_id)
                        ])

                        # Extract numeric suffixes e.g. TAX_2 → 2
                        suffix_numbers = []
                        for tax_rec in similar:
                            parts = tax_rec.name.split('_')
                            if len(parts) > 1 and parts[-1].isdigit():
                                suffix_numbers.append(int(parts[-1]))

                        next_number = (max(suffix_numbers) + 1) if suffix_numbers else 2
                        new_name = f"{name}_{next_number}"

                    # Create unique tax
                    tax = Tax.create({
                        'name': new_name,
                        'amount': rate,
                        'type_tax_use': 'sale',
                    })

                if not tax:
                    try:
                        tax = self.env['account.tax'].sudo().create({
                            'name': name,
                            'amount': rate,
                            'amount_type': 'percent',
                            'type_tax_use': 'sale',
                            'price_include': False,
                        })
                    except:
                        continue

                tax_ids.append(tax.id)

        if tax_ids:
            try:
                # ensure taxes exist (we usually created them with sudo earlier)
                tax_ids = [int(t) for t in tax_ids]

                # Decide which field to write to: sale.order.line uses 'tax_id', account.move.line uses 'tax_ids'
                if 'tax_id' in line._fields:
                    # sale.order.line style
                    line_sudo = line.sudo()
                    line_sudo.tax_id = [(6, 0, tax_ids)]
                    # recompute sale.order.line amounts if available
                    if hasattr(line_sudo, '_compute_amount'):
                        try:
                            line_sudo._compute_amount()
                        except Exception:
                            # best effort: invalidate cache so UI shows changes
                            self.invalidate_recordset()
                            line_sudo.invalidate_cache()
                elif 'tax_ids' in line._fields:
                    # account.move.line style
                    line_sudo = line.sudo()
                    line_sudo.tax_ids = [(6, 0, tax_ids)]
                    # account.move lines usually require recomputing at move level
                    move = getattr(line_sudo, 'move_id', None)
                    if move:
                        # Try common recompute methods gracefully
                        if hasattr(move, '_compute_amount'):
                            try:
                                move._compute_amount()
                            except Exception:
                                # Some account.move versions use other names; try generic invalidation
                                move.invalidate_cache()
                        else:
                            move.invalidate_cache()
                    else:
                        # fallback: try line recompute if present
                        if hasattr(line_sudo, '_compute_amount'):
                            try:
                                line_sudo._compute_amount()
                            except Exception:
                                line_sudo.invalidate_cache()
                else:
                    _logger.warning("No tax field found on %s (id=%s). Cannot set taxes.", line._name, line.id)
            except Exception as e:
                _logger.exception("Failed to assign taxes to %s (id=%s): %s", line._name, getattr(line, 'id', False), e)


        

    # --------------------------------------------------------------------
    # SHARED ACTION
    # --------------------------------------------------------------------
    def action_ceretax_calculate(self):
        for doc in self:
            payload = doc._build_ceretax_payload()
            api = self.env['ceretax.api.mixin']

            try:
                resp_http = api._ceretax_request('post', 'sale', payload, doc, None)
                result = resp_http.json()
            except Exception as e:
                raise UserError(_("CereTax API failed: %s") % e)

            doc._apply_ceretax_response(result)

        return True

    def _ceretax_get_line_qty(self, line):
        """Return quantity for both SO lines and invoice lines."""
        if hasattr(line, "quantity"):
            return line.quantity or 0.0
        if hasattr(line, "product_uom_qty"):
            return line.product_uom_qty or 0.0
        return 0.0