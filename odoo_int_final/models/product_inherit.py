# -*- coding: utf-8 -*-
from odoo import models, fields

class ProductTemplate(models.Model):
    _inherit = 'product.template'

    ceretax_ps_code_id = fields.Many2one('ceretax.ps.code', string='PS Code', ondelete='set null')

class ProductProduct(models.Model):
    _inherit = 'product.product'

    ceretax_ps_code_id = fields.Many2one('ceretax.ps.code', string='PS Code', ondelete='set null')

class ProductCategory(models.Model):
    _inherit = 'product.category'

    ceretax_ps_code_id = fields.Many2one('ceretax.ps.code', string='PS Code', ondelete='set null')
