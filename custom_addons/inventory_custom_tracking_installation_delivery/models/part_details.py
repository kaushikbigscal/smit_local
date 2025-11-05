import logging
from odoo import models, fields, api

_logger = logging.getLogger(__name__)


class CustomerProductMappingPart(models.Model):
    _name = 'customer.product.mapping.part'
    _description = 'Customer Product Mapping Parts'

    mapping_id = fields.Many2one(
        'customer.product.mapping', string='Mapping Reference', required=True, ondelete='cascade'
    )
    product_id = fields.Many2one(
        'product.template', string='Part', domain="[('is_part','=',True)]"
    )

    description = fields.Char("Description")
    part_service_type = fields.Selection([('replace', 'Replace'), ('repair', 'Repair')], string="Part Service Type")
    last_update_date_time = fields.Datetime(
        string='Last Update DateTime',
        default=lambda self: fields.Datetime.now(),
        readonly=True,
        help="Date and time of the last update to this record"
    )
    is_replace = fields.Boolean(string="Is Replace")
    original_product_id = fields.Many2one('product.product', string="part's original product id",
                                          compute='_compute_original_part_product', search=True)
    serial_number_ids = fields.Many2one(
        'stock.lot',
        string='Serial Number',
        domain="[('product_id', '=', original_product_id)]",
    )

    previous_serial_number_ids = fields.Many2one(comodel_name='stock.lot', string='Previous Serial Number', domain="[('product_id','=',original_product_id)]")
    task_id = fields.Many2one(
        'project.task',
        string='Task',  # 👈 This is the missing field!
        ondelete='cascade'
    )

    # def open_part_service_wizard(self):
    #     self.ensure_one()
    #     serial_id = self.serial_number_ids and self.serial_number_ids[0].id or False
    #     return {
    #         'type': 'ir.actions.act_window',
    #         'name': 'Update Part Service',
    #         'res_model': 'part.service.wizard',
    #         'view_mode': 'form',
    #         'target': 'new',
    #         'context': {
    #             'default_part_id': self.id,
    #             'default_serial_number_id': serial_id,
    #         },
    #     }
    @api.depends('product_id')
    def _compute_original_part_product(self):
        for record in self:
            if record.product_id:
                product = self.env['product.product'].search([('name', '=', record.product_id.name)], limit=1)
                record.original_product_id = product or False  # Always assign
            else:
                record.original_product_id = False

    # def _log_part_history(self, action, description=""):
    #     for part in self:
    #         task_ids = part.mapping_id.task_ids
    #         mapping = part.mapping_id
    #         customer = mapping.customer_id if mapping else None
    #
    #         for task in (task_ids or [None]):  # log even if no task
    #             self.env['part.history'].create({
    #                 'part_name': part.product_id.name,
    #                 'mapping_id': part.mapping_id.id,
    #                 'task_id': task.id if task else None,
    #                 'product_id': part.product_id.id,
    #                 'action': action,
    #                 'part_service_type': part.part_service_type,
    #                 'description': part.description,
    #                 'customer_id': customer.id if customer else None,
    #                 'original_product_id': part.original_product_id.id if part.original_product_id else False,
    #                 'serial_number_ids': part.serial_number_ids.id if part.serial_number_ids else False,
    #                 'previous_serial_number_ids': part.previous_serial_number_ids.id if part.previous_serial_number_ids else False,
    #
    #             })

    #
    # @api.model
    # def create(self, vals):
    #     if vals.get('part_service_type') == 'replace':
    #         vals['is_replace'] = True
    #     record = super().create(vals)
    #     record._log_part_history('create')
    #     return record

    def write(self, vals):
        vals['last_update_date_time'] = fields.Datetime.now()

        # # Apply conditional logic
        # if 'part_service_type' in vals:
        #     if vals['part_service_type'] == 'replace':
        #         vals['is_replace'] = True
        #     elif vals['part_service_type'] == 'repair':
        #         vals['is_replace'] = False

        res = super().write(vals)
        # self._log_part_history('update')
        return res

    # def unlink(self):
    #     for rec in self:
    #         rec._log_part_history('delete')
    #     return super().unlink()



class ProjectTaskPart(models.Model):
    _name = 'project.task.part'
    _description = 'Project Task Parts (Copied from Mapping)'
    customer_id = fields.Many2one(
        'res.partner',
        string='Customer',
        related='task_id.partner_id',
        store=False,
        readonly=True
    )
    mapping_id = fields.Many2one(
        'customer.product.mapping',
        string='Customer Mapping',
        related='task_id.customer_product_id',  # adjust if field name differs
        store=False,
        readonly=True
    )
    task_id = fields.Many2one('project.task', string="Calls", required=True, ondelete='cascade')
    product_id = fields.Many2one('product.template', string='Part', domain="[('is_part','=',True)]")
    description = fields.Char("Description")
    part_service_type = fields.Selection([('replace', 'Replace'), ('repair', 'Repair')], string="Part Service Type")
    is_replace = fields.Boolean(string="Is Replace")
    serial_number_id = fields.Many2one('stock.lot', string='Serial Number', domain="[('product_id', '=', original_product_id)]",)
    previous_serial_number_id = fields.Many2one('stock.lot', string='Previous Serial Number', domain="[('product_id', '=', original_product_id)]",)
    original_product_id = fields.Many2one('product.product', string="Original Product")
    last_update_date_time = fields.Datetime(
        string='Last Update DateTime',
        default=lambda self: fields.Datetime.now(),
        readonly=True,
        help="Date and time of the last update to this record"
    )
    @api.depends('product_id')
    def _compute_original_product_id(self):
        for rec in self:
            if rec.product_id:
                product = self.env['product.product'].search([('name', '=', rec.product_id.name)], limit=1)
                rec.original_product_id = product or False
            else:
                rec.original_product_id = False

    def open_part_service_wizard(self):
        self.ensure_one()
        serial_id = self.serial_number_id and self.serial_number_id[0].id or False
        return {
            'type': 'ir.actions.act_window',
            'name': 'Update Part Service',
            'res_model': 'part.service.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_part_id': self.id,
                'default_serial_number_id': serial_id,
            },
        }

    def _log_part_history(self, action, description=""):
        for part in self:
            task = part.task_id
            mapping = part.mapping_id
            customer = part.customer_id if part.customer_id else None

            self.env['part.history'].create({
                'part_name': part.product_id.name,
                'task_id': task.id if task else None,
                'mapping_id': mapping.id if mapping else None,
                'product_id': part.product_id.id,
                'action': action,
                'part_service_type': part.part_service_type,
                'description': part.description or description,
                'customer_id': customer.id if customer else None,
                'original_product_id': part.original_product_id.id if part.original_product_id else False,
                'serial_number_ids': part.serial_number_id.id if part.serial_number_id else False,
                'previous_serial_number_ids': part.previous_serial_number_id.id if part.previous_serial_number_id else False,
            })

    @api.model
    def create(self, vals):
        if vals.get('part_service_type') == 'replace':
            vals['is_replace'] = True
        record = super().create(vals)
        record._log_part_history('create')
        return record

    def write(self, vals):
        vals['last_update_date_time'] = fields.Datetime.now()

        if 'part_service_type' in vals:
            if vals['part_service_type'] == 'replace':
                vals['is_replace'] = True
            elif vals['part_service_type'] == 'repair':
                vals['is_replace'] = False

        res = super().write(vals)
        self._log_part_history('update')
        return res

    def unlink(self):
        for rec in self:
            rec._log_part_history('delete')
        return super().unlink()


class ProductMapping(models.Model):
    _inherit = 'customer.product.mapping'

    mapping_parts_ids = fields.One2many('customer.product.mapping.part', 'mapping_id', string="Parts List")

    task_ids = fields.One2many(
        'project.task',
        'customer_product_id',
        string='Related Calls')

    @api.model
    def create(self, vals):
        record = super().create(vals)

        # Auto-create mapping parts from product template parts
        if record.product_id and record.product_id.product_tmpl_id:
            tmpl = record.product_id.product_tmpl_id
            for part in tmpl.part_ids:
                if part.display_name:
                    self.env['customer.product.mapping.part'].create({
                        'mapping_id': record.id,
                        'product_id': part.display_name.id,
                    })

        return record

    def write(self, vals):
        res = super().write(vals)

        if 'product_id' in vals:
            for record in self:
                if record.product_id and record.product_id.product_tmpl_id:
                    # Step 1: Remove existing mapping parts
                    record.mapping_parts_ids.unlink()

                    # Step 2: Create new mapping parts from the template
                    tmpl = record.product_id.product_tmpl_id
                    for part in tmpl.part_ids:
                        if part.display_name:
                            self.env['customer.product.mapping.part'].create({
                                'mapping_id': record.id,
                                'product_id': part.display_name.id,
                            })

        return res

class ProjectTask(models.Model):
    _inherit = 'project.task'

    task_part_ids = fields.One2many(
        'project.task.part',
        'task_id',
        string="Parts List",
    )

    @api.model
    def create(self, vals):
        task = super().create(vals)

        stage = self.env['project.task.type'].browse(vals.get('stage_id')) if vals.get('stage_id') else None

        if stage and task.customer_product_id:
            # CASE 1: Assigned → Copy mapping_parts_ids → task_part_ids
            if stage.name == 'Assigned' or stage.name == 'New' and not task.task_part_ids:
                for mapping_part in task.customer_product_id.mapping_parts_ids:
                    self.env['project.task.part'].create({
                        'task_id': task.id,
                        'product_id': mapping_part.product_id.id,
                        'description': mapping_part.description,
                        'part_service_type': mapping_part.part_service_type,
                        'is_replace': mapping_part.is_replace,
                        'original_product_id': mapping_part.original_product_id.id,
                        'serial_number_id': mapping_part.serial_number_ids.id,
                        'previous_serial_number_id': mapping_part.previous_serial_number_ids.id,
                    })

            # CASE 2: Done → Copy task_part_ids → mapping_parts_ids (if any)
            elif stage.name == 'Done' and task.task_part_ids:
                # First remove existing mapping parts
                task.customer_product_id.mapping_parts_ids.unlink()

                # Then copy task parts to mapping parts
                for task_part in task.task_part_ids:
                    self.env['customer.product.mapping.part'].create({
                        'mapping_id': task.customer_product_id.id,
                        'product_id': task_part.product_id.id,
                        'description': task_part.description,
                        'part_service_type': task_part.part_service_type,
                        'is_replace': task_part.is_replace,
                        'original_product_id': task_part.original_product_id.id,
                        'serial_number_ids': task_part.serial_number_id.id,
                        'previous_serial_number_ids': task_part.previous_serial_number_id.id,
                    })

        return task

    def write(self, vals):
        res = super(ProjectTask, self).write(vals)

        if 'stage_id' in vals:
            stage = self.env['project.task.type'].browse(vals['stage_id'])

            for task in self:
                # 1. Copy mapping_parts → task_parts when assigned
                if stage.name == 'Assigned' or stage.name == 'New':
                    if task.customer_product_id and not task.task_part_ids:
                        for mapping_part in task.customer_product_id.mapping_parts_ids:
                            self.env['project.task.part'].create({
                                'task_id': task.id,
                                'product_id': mapping_part.product_id.id,
                                'description': mapping_part.description,
                                'part_service_type': mapping_part.part_service_type,
                                'is_replace': mapping_part.is_replace,
                                'original_product_id': mapping_part.original_product_id.id,
                                'serial_number_id': mapping_part.serial_number_ids.id,
                                'previous_serial_number_id': mapping_part.previous_serial_number_ids.id,
                            })

                # 2. Copy task_parts → mapping_parts when done
                elif stage.name == 'Done':
                    if task.customer_product_id:
                        # Remove existing mapping parts
                        task.customer_product_id.mapping_parts_ids.unlink()

                        # Create new mapping parts from task parts
                        for task_part in task.task_part_ids:
                            self.env['customer.product.mapping.part'].create({
                                'mapping_id': task.customer_product_id.id,
                                'product_id': task_part.product_id.id,
                                'description': task_part.description,
                                'part_service_type': task_part.part_service_type,
                                'is_replace': task_part.is_replace,
                                'original_product_id': task_part.original_product_id.id,
                                'serial_number_ids': task_part.serial_number_id.id,
                                'previous_serial_number_ids': task_part.previous_serial_number_id.id,
                            })

        return res
