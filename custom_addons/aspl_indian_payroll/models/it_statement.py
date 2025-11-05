# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

import calendar
from datetime import datetime, date, timedelta
import fiscalyear
from odoo.http import request
from odoo import models, api
import logging
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class HrEmoloyee(models.Model):
    _inherit = 'hr.employee'

    def calculation_ytd_summary_it_statement_data(self, ytd_summary_it_statement_data, contract_run_obj, month):
        _logger.info(f"Starting YTD summary calculation for month {month}")
        _logger.info(f"Initial YTD summary data: {ytd_summary_it_statement_data}")
        _logger.info(f"Contract object ID: {contract_run_obj.id}")

        ytd_summary_it_statement_data_2 = ytd_summary_it_statement_data

        _logger.info(f"Number of applicable salary rules: {len(contract_run_obj.applicable_salary_rule_ids)}")

        for line in contract_run_obj.applicable_salary_rule_ids:
            _logger.info(f"Processing salary rule line: {line.id}")

            if "Newid" in str(line.id):
                _logger.info(f"Skipping line with Newid: {line.id}")
                continue

            if line.rule_id.taxable or line.rule_id.is_deduction:
                a = 'Income' if line.rule_id.taxable else 'Deduction'
                _logger.info(f"Processing {a} line: {line.rule_id.name}, Amount: {line.amount}")

                if ytd_summary_it_statement_data_2.get(a):
                    _logger.info(f"{a} category exists in YTD summary")

                    if ytd_summary_it_statement_data_2.get(a).get(line.rule_id.name):
                        _logger.debug(f"{line.rule_id.name} exists in {a} category")

                        if ytd_summary_it_statement_data_2.get(a).get(line.rule_id.name).get(month):
                            _logger.debug(f"Amount already exists for {line.rule_id.name} in month {month}")
                        else:
                            ytd_summary_it_statement_data_2.get(a).get(line.rule_id.name)[month] = line.amount
                            _logger.info(f"Added amount {line.amount} for {line.rule_id.name} in month {month}")
                    else:
                        ytd_summary_it_statement_data_2.get(a)[line.rule_id.name] = {month: line.amount}
                        _logger.info(
                            f"Created new entry for {line.rule_id.name} with amount {line.amount} in month {month}")
                else:
                    ytd_summary_it_statement_data_2[a] = {line.rule_id.name: {month: line.amount}}
                    _logger.info(
                        f"Created new {a} category with {line.rule_id.name} and amount {line.amount} in month {month}")
            else:
                _logger.debug(f"Skipping non-taxable and non-deduction line: {line.rule_id.name}")

        _logger.info(f"YTD summary calculation completed for month {month}")
        _logger.debug(f"Final YTD summary data for month {month}: {ytd_summary_it_statement_data_2}")

        return ytd_summary_it_statement_data_2

    @api.model
    def get_user_employee_details_payslip(self):
        _logger.info("Starting get_user_employee_details_payslip")

        current_user = self.env.user
        _logger.debug(f"Current user: {current_user.name} (ID: {current_user.id})")

        # Find the employee record associated with the current user
        employee = self.env['hr.employee'].sudo().search([('user_id', '=', current_user.id)], limit=1)

        today = date.today()

        if not employee:
            _logger.warning("Employee Not Found")
            return "Employee Not Found..."

        _logger.info(f"Processing employee: {employee.name}")

        # ********************* YTD SUMMARY IT STATEMENT TABLE ********************* #

        ytd_summary_it_statement_data = {
            'Income': {},
            'Deduction': {
                'Total': {
                    'Total': 0.0
                },
                'Provident Fund (Employer Contribution)': {
                    'Total': 0.0
                }
            }
        }

        fiscalyear.START_MONTH = 4
        currentfiscalstart = fiscalyear.FiscalYear(
            datetime.now().year).start.date() if datetime.now().month < 4 else fiscalyear.FiscalYear(
            datetime.now().year + 1).start.date()
        # currentfiscalstart = date(2025, 4, 1)
        print(f"#current fiscal year", currentfiscalstart)
        currentfiscalend = fiscalyear.FiscalYear(
            datetime.now().year).end.date() if datetime.now().month < 4 else fiscalyear.FiscalYear(
            datetime.now().year + 1).end.date()
        # currentfiscalend = date(2026, 4, 1)

        _logger.info(f"Fiscal year start: {currentfiscalstart}, end: {currentfiscalend}")

        for month in range(1, 13):
            _logger.info(f"Processing month: {month}")
            if month in [1, 2, 3]:
                date_start = date(currentfiscalend.year, month, 1)
                _, date_end = calendar.monthrange(currentfiscalend.year, month)
                date_end = date(currentfiscalend.year, month, date_end)
            else:
                date_start = date(currentfiscalstart.year, month, 1)
                _, date_end = calendar.monthrange(currentfiscalstart.year, month)
                date_end = date(currentfiscalstart.year, month, date_end)

            payslip_obj = self.env['hr.payslip'].search(
                [('employee_id', '=', employee.id), ('date_from', '>=', date_start), ('date_to', '<=', date_end),
                 ('state', '!=', 'cancel')])
            contract_obj = self.env['hr.contract'].search(
                [('employee_id', '=', employee.id), ('date_start', '<=', date_start), ('date_end', '>=', date_end),
                 ('state', '!=', 'cancel')])

            _logger.info(f"Payslips found: {len(payslip_obj)}, Contracts found: {len(contract_obj)}")

            if payslip_obj:
                _logger.debug("Processing payslip")
                for line in payslip_obj.line_ids:
                    if "Newid" in str(line.id):
                        continue
                    if line.salary_rule_id.taxable or line.salary_rule_id.is_deduction:
                        a = 'Income' if line.salary_rule_id.taxable else 'Deduction'
                        if ytd_summary_it_statement_data.get(a):
                            if ytd_summary_it_statement_data.get(a).get(line.salary_rule_id.name):
                                if ytd_summary_it_statement_data.get(a).get(line.salary_rule_id.name).get(month):
                                    pass
                                else:
                                    ytd_summary_it_statement_data.get(a).get(line.salary_rule_id.name)[
                                        month] = line.amount
                            else:
                                ytd_summary_it_statement_data.get(a)[line.salary_rule_id.name] = {month: line.amount}
                        else:
                            ytd_summary_it_statement_data[a] = {line.salary_rule_id.name: {month: line.amount}}
            elif contract_obj:
                _logger.debug("Processing contract")
                contract_run_obj = contract_obj.filtered(lambda obj: obj.state == 'open')
                contract_new_obj = contract_obj.filtered(lambda obj: obj.state == 'draft')
                contract_exp_obj = contract_obj.filtered(lambda obj: obj.state == 'close')

                if contract_run_obj:
                    ytd_summary_it_statement_data = self.calculation_ytd_summary_it_statement_data(
                        ytd_summary_it_statement_data, contract_run_obj, month)
                elif contract_new_obj:
                    ytd_summary_it_statement_data = self.calculation_ytd_summary_it_statement_data(
                        ytd_summary_it_statement_data, contract_new_obj, month)
                elif contract_exp_obj:
                    ytd_summary_it_statement_data = self.calculation_ytd_summary_it_statement_data(
                        ytd_summary_it_statement_data, contract_exp_obj, month)
            else:
                _logger.debug("No payslip or contract found for the month")
                if date(today.year, today.month, 1) <= date_start:
                    first_day_of_current_month = today.replace(day=1)
                    last_day_of_previous_month = first_day_of_current_month - timedelta(days=1)
                    first_day_of_previous_month = last_day_of_previous_month.replace(day=1)

                    last_month_payslip = self.env['hr.payslip'].search(
                        [('employee_id', '=', employee.id), ('date_from', '>=', first_day_of_previous_month),
                         ('date_to', '<=', last_day_of_previous_month), ('state', '!=', 'cancel')])
                    last_month_contract = self.env['hr.contract'].search(
                        [('employee_id', '=', employee.id), ('date_start', '<=', first_day_of_previous_month),
                         ('date_end', '>=', last_day_of_previous_month), ('state', '!=', 'cancel')])

                    if last_month_payslip or last_month_contract:
                        lat_contract_obj = self.env['hr.contract'].search(
                            [('employee_id', '=', employee.id), ('state', '!=', 'cancel')], limit=1,
                            order='id desc')
                        if lat_contract_obj:
                            ytd_summary_it_statement_data = self.calculation_ytd_summary_it_statement_data(
                                ytd_summary_it_statement_data, lat_contract_obj, month)

        _logger.info("YTD summary calculation completed")
        _logger.info("Donee")
        # Add Empty Month Values
        _logger.debug("Adding empty month values")
        month_counter = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12]
        for i in ytd_summary_it_statement_data:
            if i not in ['Income', 'Deduction']:
                continue
            for j, k in ytd_summary_it_statement_data[i].items():
                if not isinstance(k, dict):
                    continue
                for mc in month_counter:
                    if mc not in k:
                        k[mc] = 0
                sorted_items = []
                for key in range(1, 13):
                    if key in k:
                        sorted_items.append((key, k[key]))
                sorted_dict = dict(sorted_items)
                ytd_summary_it_statement_data[i][j] = sorted_dict

        # Add Year Total & Manage Sequence of Months.
        _logger.debug("Adding year total and managing sequence of months")
        total_of_months = 0
        for i in ytd_summary_it_statement_data:
            for j in ytd_summary_it_statement_data[i]:
                items = list(ytd_summary_it_statement_data[i][j].items())
                for key, value in ytd_summary_it_statement_data[i][j].items():
                    total_of_months += value
                items.insert(0, ('Total', total_of_months))
                total_of_months = 0
                ytd_summary_it_statement_data[i][j] = dict(items)

        # Add All Total.
        _logger.debug("Adding all total")
        for i in ytd_summary_it_statement_data:
            temp_dict = {}
            for j in ytd_summary_it_statement_data[i]:
                for key, value in ytd_summary_it_statement_data[i][j].items():
                    if temp_dict.get('Total'):
                        if temp_dict.get('Total').get(key):
                            temp_dict['Total'][key] += value
                        else:
                            temp_dict.get('Total')[key] = value
                    else:
                        temp_dict['Total'] = {key: value}
            ytd_summary_it_statement_data.get(i).update(temp_dict)

        if ytd_summary_it_statement_data:
            _logger.info("Calculating tax")
            # Tax Calculation
            taxable_amount = ytd_summary_it_statement_data['Income']['Total']['Total']
            _logger.debug(f"Initial taxable amount: {taxable_amount}")

            _, month_end_dt = calendar.monthrange(today.year, today.month)
            month_end_dt = date(today.year, today.month, month_end_dt)
            it_declaration_info = employee.get_it_statement_info(month_end_dt)

            it_components = it_declaration_info[0]

            ytd_summary_it_deduction_component_last_employer = {}
            ytd_summary_it_deduction_component_last_employer['Total Income After Exemptions'] = it_declaration_info[
                1].income_after_exemptions
            ytd_summary_it_deduction_component_last_employer['Professional Tax'] = it_declaration_info[
                1].professional_tax
            ytd_summary_it_deduction_component_last_employer['Provident Fund'] = it_declaration_info[
                1].provident_fund
            ytd_summary_it_deduction_component_last_employer['Total Tax'] = it_declaration_info[
                1].total_tax_previous_employer

            print("Last Employement", ytd_summary_it_deduction_component_last_employer)

            totalbasic = ytd_summary_it_statement_data['Income']['Basic Salary']['Total']
            print(totalbasic)
            totalhra = ytd_summary_it_statement_data['Income']['House Rent Allowance']['Total']
            print(totalhra)
            rent_paid = it_components['house_rent']
            print(rent_paid)
            formula = []
            formula_1 = totalhra
            print(formula_1)
            # if employee.private_city.lower() in ["mumbai", "calcutta", "delhi", "chennai"]:
            #     formula_2 = totalbasic * 0.5
            # else:
            #     formula_2 = totalbasic * 0.4

            if employee.private_city:
                if employee.private_city.lower() in ["mumbai", "calcutta", "delhi", "chennai"]:
                    formula_2 = totalbasic * 0.5
                else:
                    formula_2 = totalbasic * 0.4
            else:
                raise UserError("Please Add City in Employee Form (Private Information) Before Accessing IT Statement")

            print(formula_2)
            formula_3 = rent_paid - (0.1 * totalbasic)
            print(formula_3)
            formula_3 = 0 if formula_3 < 0 else formula_3
            print(formula_3)
            formula.append(formula_1)
            formula.append(formula_2)
            formula.append(formula_3)
            hra_exempted_amount = min(formula)
            print(formula)
            print(hra_exempted_amount)

            gratuity_from_previous_system = it_components.get('gratuity_from_previous_system')
            tax_prev_emp = it_components.get('tax_on_income')
            surcharge_prev_emp = it_components.get('surcharge')
            ecess_prev_emp = it_components.get('ecess')
            total_paid_tax = employee.cummulative_tax()

            pt = 0
            if it_components.get('previous_employer_professional_tax') != 0:
                pt += it_components.get('previous_employer_professional_tax')
                if employee.join_date.month >= 4:
                    pt += (16 - employee.join_date.month) * 200
                else:
                    pt += (4 - employee.join_date.month) * 200
            else:
                pt = 2400

            # pf = 0
            # if it_components.get('previous_employer_pf_employer') != 0:
            #     pf += it_components.get('previous_employer_pf_employer')
            #     if employee.join_date.month >= 4:
            #         pf += (16 - employee.join_date.month) * 1950
            #     else:
            #         pf += (4 - employee.join_date.month) * 1950
            # else:
            #     pf = 23400

            standard_deduction = 50000
            new_standard_deduction = 75000

            # ytd_summary_it_deduction_components = {}
            old_regime_employer_contribution = ytd_summary_it_statement_data['Deduction']['Provident Fund (Employer Contribution)']['Total']

            ytd_summary_it_deduction_components = {
                'HRA Exempted Amount': hra_exempted_amount,
                'Professional Tax': pt,
                'Standard Deduction': standard_deduction,
                '80C': it_components['80c'],
                '80CCD': it_components['80ccd'],
                '80D': it_components['80d'],
                '80 Other': it_components['80other'],
                '80CCD(2) Employer Contribution': old_regime_employer_contribution}

            ytd_summary_it_deduction_components_new = {'HRA Exempted Amount': hra_exempted_amount,
                                                       'Professional Tax': 0,
                                                       'Standard Deduction': new_standard_deduction,
                                                       '80C': it_components['80c'], '80CCD': it_components['80ccd'],
                                                       '80D': it_components['80d'], '80 Other': it_components['80other']}

            ytd_summary_it_income_components = {'Other Income': it_components['other_income'],
                                                'Income/Loss House Property': it_components[
                                                    'income_lose_house_property']}

            ytd_summary_it_income_components_new = {'Other Income': it_components['other_income'],
                                                    'Income/Loss House Property': max(0, it_components[
                                                        'income_lose_house_property_new'])}

            # ===================================== OLD REGIME =====================================
            for key, values in ytd_summary_it_deduction_components.items():
                taxable_amount -= values
            for key, values in ytd_summary_it_income_components.items():
                taxable_amount += values
            taxable_amount += ytd_summary_it_deduction_component_last_employer['Total Income After Exemptions']
            taxable_amount -= ytd_summary_it_deduction_component_last_employer['Provident Fund']

            old_regime_tax = employee.old_regime_calculation(taxable_amount, ecess_prev_emp, surcharge_prev_emp,
                                                             tax_prev_emp, total_paid_tax)
            taxo_old_regime = old_regime_tax[1]
            surchargeo_old_regime = old_regime_tax[3]
            cesso_old_regime = old_regime_tax[2]
            grayhr_old_regime = old_regime_tax[4]
            tottaxo_old_regime = old_regime_tax[0]
            old_rebate_amount = old_regime_tax[-1]

            # ===================================== NEW REGIME =====================================
            taxable_amount_new_regime = ytd_summary_it_statement_data['Income']['Total']['Total'] - \
                                        ytd_summary_it_statement_data['Deduction'][
                                            'Provident Fund (Employer Contribution)']['Total']
            for key, values in ytd_summary_it_income_components_new.items():
                taxable_amount_new_regime += values
            taxable_amount_new_regime += ytd_summary_it_deduction_component_last_employer[
                'Total Income After Exemptions']
            pf = ytd_summary_it_deduction_component_last_employer['Provident Fund']
            taxable_amount_new_regime -= ytd_summary_it_deduction_component_last_employer['Provident Fund']
            taxable_amount_new_regime -= new_standard_deduction

            new_regime_tax = employee.new_regime_calculation(taxable_amount_new_regime, ecess_prev_emp,
                                                             surcharge_prev_emp, tax_prev_emp, total_paid_tax)
            taxo_new_regime = new_regime_tax[1]
            surchargen_new_regime = new_regime_tax[3]
            cessn_new_regime = new_regime_tax[2]
            grayhr_new_regime = new_regime_tax[4]
            tottaxo_new_regime = new_regime_tax[0]
            rebate_amount = new_regime_tax[-1]

            _logger.debug(f"Old regime tax: {tottaxo_old_regime}, New regime tax: {tottaxo_new_regime}")
            if taxable_amount < 0:
                taxable_amount = 0
            if taxable_amount_new_regime < 0:
                taxable_amount_new_regime = 0

            salary_component = {
                'Gross Salary': ytd_summary_it_statement_data['Income']['Total']['Total'],
                'HRA Exempted Amount': hra_exempted_amount,
                'Salary after Exemptions': ytd_summary_it_statement_data['Income']['Total']['Total'] - hra_exempted_amount
            }
            tax_amount_old_regime_dict = {'Basic Tax': round(taxo_old_regime),
                                          'Less: Rebate u/s87A': round(old_rebate_amount),
                                          'Tax After Rebate': round(taxo_old_regime) - round(old_rebate_amount),
                                          'Surcharge': round(surchargeo_old_regime),
                                          'Health & Edu.Cess': round(cesso_old_regime),
                                          # 'Accumulated Gratuity(From previous system)': "{:.2f}".format(grayhr_old_regime),
                                          'Total Tax Amount': round(tottaxo_old_regime)}

            tax_amount_new_regime_dict = {
                'Basic Tax': round(taxo_new_regime),
                'Less: Rebate u/s87A': round(rebate_amount),
                'Tax After Rebate': round(taxo_new_regime) - round(rebate_amount),
                'Surcharge': round(surchargen_new_regime),
                'Health & Edu.Cess': round(cessn_new_regime),
                # 'Accumulated Gratuity(From previous system)': round(grayhr_new_regime),
                'Total Tax Amount': round(tottaxo_new_regime)
            }

            data = {
                'employee_name': employee.name,
                'current_financial_year': it_declaration_info[1].financial_year.name,
                'ytd_summary_it_statement_data': ytd_summary_it_statement_data,
                'ytd_summary_it_income_components': ytd_summary_it_income_components,
                'ytd_summary_it_income_components_new': ytd_summary_it_income_components_new,
                'ytd_summary_it_deduction_component_last_employer': ytd_summary_it_deduction_component_last_employer,
                'ytd_summary_it_deduction_components': ytd_summary_it_deduction_components,
                'ytd_summary_it_deduction_components_new': ytd_summary_it_deduction_components_new,
                'tax_amount_old_regime_dict': tax_amount_old_regime_dict,
                'tax_amount_new_regime_dict': tax_amount_new_regime_dict,
                'salary_component': salary_component
            }
            _logger.info("Successfully generated employee payslip details")
            return data
        else:
            _logger.warning("Employee Payslip or It Declaration Not Found")
            return "Employee Payslip or It Declaration Not Found..."
