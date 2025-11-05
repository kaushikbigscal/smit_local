# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from collections import defaultdict
import re
from odoo import models, api, fields, _


class DataRecycleRecord(models.Model):
    _name = 'data_recycle.record'
    _description = 'Recycling Record'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    active = fields.Boolean('Active', default=True)
    name = fields.Char('Record Name', compute='_compute_name', compute_sudo=True)
    recycle_model_id = fields.Many2one('data_recycle.model', string='Recycle Model', ondelete='cascade')

    res_id = fields.Integer('Record ID', index=True)
    res_model_id = fields.Many2one(related='recycle_model_id.res_model_id', store=True, readonly=True)
    res_model_name = fields.Char(related='recycle_model_id.res_model_name', store=True, readonly=True)

    company_id = fields.Many2one('res.company', compute='_compute_company_id', store=True)
    is_deleted = fields.Boolean('Deleted', default=False)

    is_archived = fields.Boolean('Archived', default=False)
    @api.model
    def _get_company_id(self, record):
        company_id = self.env['res.company']
        if 'company_id' in self.env[record._name]:
            company_id = record.company_id
        return company_id

    @api.depends('res_id')
    def _compute_name(self):
        original_records = {(r._name, r.id): r for r in self._original_records()}
        for record in self:
            original_record = original_records.get((record.res_model_name, record.res_id))
            if original_record:
                record.name = original_record.display_name or _('Undefined Name')
            else:
                record.name = _('**Record Deleted**')

    @api.depends('res_id')
    def _compute_company_id(self):
        original_records = {(r._name, r.id): r for r in self._original_records()}
        for record in self:
            original_record = original_records.get((record.res_model_name, record.res_id))
            if original_record:
                record.company_id = self._get_company_id(original_record)
            else:
                record.company_id = self.env['res.company']

    def _original_records(self):
        if not self:
            return []

        records = []
        records_per_model = {}
        for record in self.filtered(lambda r: r.res_model_name):
            ids = records_per_model.get(record.res_model_name, [])
            ids.append(record.res_id)
            records_per_model[record.res_model_name] = ids

        for model, record_ids in records_per_model.items():
            recs = self.env[model].with_context(active_test=False).sudo().browse(record_ids).exists()
            records += [r for r in recs]
        return records

    # def action_validate(self):
    #     records_done = self.env['data_recycle.record']
    #     record_ids_to_archive = defaultdict(list)
    #     record_ids_to_unlink = defaultdict(list)
    #     original_records = {'%s_%s' % (r._name, r.id): r for r in self._original_records()}
    #     for record in self:
    #         original_record = original_records.get('%s_%s' % (record.res_model_name, record.res_id))
    #         records_done |= record
    #         if not original_record:
    #             continue
    #         if record.recycle_model_id.recycle_action == "archive":
    #             record_ids_to_archive[original_record._name].append(original_record.id)
    #         elif record.recycle_model_id.recycle_action == "unlink":
    #             record_ids_to_unlink[original_record._name].append(original_record.id)
    #     for model_name, ids in record_ids_to_archive.items():
    #         self.env[model_name].sudo().browse(ids).toggle_active()
    #         self.filtered(lambda r: r.res_id in ids and r.res_model_name == model_name).write({'is_archived': True})
    #     for model_name, ids in record_ids_to_unlink.items():
    #         self.env[model_name].sudo().browse(ids).unlink()
    #         self.filtered(lambda r: r.res_id in ids and r.res_model_name == model_name).write({'is_deleted': True})
    #     records_done.unlink()

    def strip_html_tags(self, text):
        import re
        import html as html_module
        clean = re.compile('<.*?>')
        # First unescape HTML entities, then remove tags
        return re.sub(clean, '', html_module.unescape(text))

    def action_validate(self):
        records_done = self.env['data_recycle.record']
        record_ids_to_archive = defaultdict(list)
        record_ids_to_unlink = defaultdict(list)
        original_records = {'%s_%s' % (r._name, r.id): r for r in self._original_records()}
        error_records = self.env['data_recycle.record']

        # Prepare lists of records to process
        for record in self:
            original_record = original_records.get('%s_%s' % (record.res_model_name, record.res_id))
            records_done |= record
            if not original_record:
                continue
            if record.recycle_model_id.recycle_action == "archive":
                record_ids_to_archive[original_record._name].append((record, original_record.id))
            elif record.recycle_model_id.recycle_action == "unlink":
                record_ids_to_unlink[original_record._name].append((record, original_record.id))

        # Archive records, handle errors per record
        for model_name, recs in record_ids_to_archive.items():
            for record, rec_id in recs:
                try:
                    self.env[model_name].sudo().browse(rec_id).toggle_active()
                    record.is_archived = True
                except Exception as err:
                    error_message = f"Error during archive for record {record.res_id}: {str(err)}"
                    record._post_error_to_chatter(error_message)
                    error_records |= record

        # Delete records, handle errors per record
        for model_name, recs in record_ids_to_unlink.items():
            for record, rec_id in recs:
                try:
                    self.env[model_name].sudo().browse(rec_id).unlink()
                    record.is_deleted = True
                except Exception as err:
                    error_message = f"Error during delete for record {record.res_id}: {str(err)}"
                    record._post_error_to_chatter(error_message)
                    error_records |= record

        # Unlink only records that succeeded
        (records_done - error_records).unlink()

    def action_discard(self):
        self.write({'active': False})


    # dhruti
    def _post_error_to_chatter(self, error_message):
        self.message_post(
            body=f"<b>Deletion Error:</b> {error_message}",
            message_type='notification',
            subtype_xmlid='mail.mt_note'
        )

    # def _delete_projects(self):
    #     projects = self.env['project.project'].sudo().read_group([('id', 'in', self.res_id)], ['id', 'name'], ['id'])
    #     failed_projects = []
    #     for project_id, project_name in projects:
    #         try:
    #             self.env['project.project'].sudo().browse(project_id).unlink()
    #         except Exception as err:
    #             error_message = f"Project ID: {project_id}, Name: {project_name}, Error: {str(err)}"
    #             failed_projects.append(error_message)
    #             self._post_error_to_chatter(error_message)
    #     if failed_projects:
    #         self.message_post(
    #             body=f"<b>Deletion Errors:</b><br>{'<br>'.join(failed_projects)}",
    #             message_type='notification',
    #             subtype_xmlid='mail.mt_note'
    #         )

    def action_view_error_log(self, log_type):
        domain = [('is_archived', '=', True)] if log_type == 'archived' else [('is_deleted', '=', True)]
        records = self.search(domain)
        error_messages = []
        for rec in records:
            last_error = rec.message_ids.filtered(lambda m: 'Error' in m.body)
            if last_error:
                error_messages.append(
                    f"Recycle Rule: {rec.recycle_model_id.display_name or '-'}\n"
                    f"Record Name: {rec.name or '-'}\n"
                    f"Record ID: {rec.res_id or '-'}\n"
                    f"Error: {self.strip_html_tags(last_error[-1].body)}\n"
                    "-----------------------------"
                )
        error_log = '\n\n'.join(error_messages) or 'No error logs found.'
        title = "Archive Error Log" if log_type == 'archived' else "Delete Error Log"
        wizard = self.env['data.recycle.error.wizard'].create({'error_log': error_log})
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'data.recycle.error.wizard',
            'res_id': wizard.id,
            'view_mode': 'form',
            'target': 'new',
        }


