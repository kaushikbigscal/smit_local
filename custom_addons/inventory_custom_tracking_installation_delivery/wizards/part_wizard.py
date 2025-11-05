from odoo import models, fields, api


class PartServiceWizard(models.TransientModel):
    _name = 'part.service.wizard'
    _description = 'Part Service Wizard'

    part_id = fields.Many2one('project.task.part', string='Part', required=True, readonly=True)

    part_service_type = fields.Selection(
        [('replace', 'Replace'), ('repair', 'Repair')],
        string="Part Service Type",
        required=True
    )

    description = fields.Char("Description")

    serial_number_id = fields.Many2one(
        'stock.lot',
        string='Serial Number',
        domain="[('product_id', '=', original_product_id)]"
    )

    previous_serial_number_ids = fields.Many2one(
        comodel_name='stock.lot',
        string='Previous Serial Number',
        domain="[('product_id','=',original_product_id)]"
    )

    original_product_id = fields.Many2one(
        related='part_id.original_product_id',
        string="Original Product",
        readonly=True
    )

    is_replace = fields.Boolean(string="Is Replace")

    actual_product_id = fields.Many2one(
        'product.product',
        string="Part",
        compute='_compute_actual_product_id',
        store=False
    )

    @api.depends('original_product_id')
    def _compute_actual_product_id(self):
        for wizard in self:
            wizard.actual_product_id = wizard.original_product_id.product_variant_id if wizard.original_product_id else False

    @api.onchange('part_service_type')
    def _onchange_service_type(self):
        self.is_replace = (self.part_service_type == 'replace')
        if self.is_replace:
            self.previous_serial_number_ids = self.serial_number_id
            self.serial_number_id = False
        else:
            self.previous_serial_number_ids = False

    def apply_service_update(self):
        self.ensure_one()
        self.part_id.write({
            'part_service_type': self.part_service_type,
            'serial_number_id': self.serial_number_id.id,
            'previous_serial_number_id': self.previous_serial_number_ids.id,
            'description': self.description,
        })


