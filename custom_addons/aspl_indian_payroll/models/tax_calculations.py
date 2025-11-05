# -*- coding: utf-8 -*-

# Part of Odoo. See LICENSE file for full copyright and licensing details.
from datetime import datetime, date
from dateutil.relativedelta import relativedelta
from odoo.exceptions import ValidationError

from odoo import models, api, fields


class FinancialYear(models.Model):
    _name = 'financial.year'

    name = fields.Char(string="Financial Year")


class ItDeclarationPayslip(models.Model):
    _name = 'it.declaration.payslip'
    _rec_name = 'employee_id'

    employee_id = fields.Many2one('hr.employee', string="Employee")
    employee_age = fields.Integer(string="Age", compute="_compute_employee_age", store=True)
    financial_year = fields.Many2one('financial.year', string="Financial Year", tracking=True, required=True)
    status = fields.Selection([
        ("locked", "Locked"),
        ("unlocked", "Unlocked"),
        ("submitted", "Submitted"),
    ],
        tracking=True,
        string="Status"

    )
    tax_regime = fields.Selection([('old_regime', 'Old'), ('new_regime', 'New')], string='Regime', required=True)
    grand_total = fields.Float(string="Total", default=0, compute='onchange_total_calculation')
    gratuity_from_previous_system = fields.Float()

    # Sec 80C
    employee_provident_fund = fields.Integer(string="80C Employee Provident Fund", tracking=True)
    five_year_fixed_deposite = fields.Integer(string="80C Five Years of Fixed Deposit in Scheduled Bank",
                                              tracking=True)
    children_tution_fees = fields.Integer(string="80C Children Tuition Fees", tracking=True)
    contribution_to_pension_fund = fields.Integer(string="80CCC Contribution to Pension Fund", tracking=True)
    deposite_in_nsc = fields.Integer(string="80C Deposit in NSC", tracking=True)
    deposite_in_nss = fields.Integer(string="80C Deposit in NSS", tracking=True)
    deposite_in_post_office = fields.Integer(string="80C Deposit in Post Office Savings Schemes", tracking=True)
    equity_linked_saving_scheme = fields.Integer(string="80C Equity Linked Savings Scheme ( ELSS )", tracking=True)
    interest_on_nsc = fields.Integer(string="80C Interest on NSC Reinvested", tracking=True)
    kisan_vikas_patra = fields.Integer(string="80C Kisan Vikas Patra (KVP)", tracking=True)
    life_insurance_premium = fields.Integer(string="80C Life Insurance Premium", tracking=True)
    long_term_infrastructure_bond = fields.Integer(string="80C Long term Infrastructure Bonds", tracking=True)
    mutual_funds = fields.Integer(string="80C Mutual Funds", tracking=True)
    nabard_rural_funds = fields.Integer(string="80C NABARD Rural Bonds", tracking=True)
    national_pension_scheme = fields.Integer(string="80C National Pension Scheme", tracking=True)
    nhb_scheme = fields.Integer(string="80C NHB Scheme", tracking=True)
    post_office_time_deposite = fields.Integer(string="80C Post office time deposit for 5 years", tracking=True)
    pradhan_mantri_suraksha_bima = fields.Integer(string="80C Pradhan Mantri Suraksha Bima Yojana", tracking=True)
    public_provident_fund = fields.Integer(string="80C Public Provident Fund", tracking=True)
    repayment_of_housing_loan = fields.Integer(string="80C Repayment of Housing loan(Principal amount)", tracking=True)
    stamp_duty_registration_charges = fields.Integer(string="80C Stamp duty and Registration charges", tracking=True)
    sukanya_samriddhi_yojana = fields.Integer(string="80C Sukanya Samriddhi Yojana", tracking=True)
    unit_linked_insurance_premium = fields.Integer(string="80C Unit Linked Insurance Premium (ULIP)", tracking=True)
    total_declared_80c = fields.Integer(compute='onchange_function_80c', string="Total declared in ?", tracking=True)
    applicable_declared_80c = fields.Integer(string="Applicable amount declared in ?", tracking=True)

    show_employee_provident_fund = fields.Boolean(
        compute="_compute_show_employee_provident_fund",
        store=False
    )

    @api.depends('employee_id.pf_employee')
    def _compute_show_employee_provident_fund(self):
        for rec in self:
            rec.show_employee_provident_fund = rec.employee_id.pf_employee if rec.employee_id else False


    @api.depends('employee_id.birthday')
    def _compute_employee_age(self):
        """Compute the employee's age based on their birthday."""
        today = fields.Date.today()
        for record in self:
            if record.employee_id.birthday:
                birth_date = record.employee_id.birthday
                record.employee_age = today.year - birth_date.year - (
                        (today.month, today.day) < (birth_date.month, birth_date.day))
            else:
                record.employee_age = 0  # Default if no birthday is set

    @api.onchange('five_year_fixed_deposite', 'employee_provident_fund', 'children_tution_fees', 'contribution_to_pension_fund', 'deposite_in_nsc',
                  'deposite_in_nss', 'deposite_in_post_office', 'equity_linked_saving_scheme', 'interest_on_nsc',
                  'kisan_vikas_patra', 'life_insurance_premium', 'long_term_infrastructure_bond', 'mutual_funds',
                  'nabard_rural_funds', 'national_pension_scheme', 'nhb_scheme', 'post_office_time_deposite',
                  'pradhan_mantri_suraksha_bima', 'public_provident_fund', 'repayment_of_housing_loan',
                  'stamp_duty_registration_charges', 'sukanya_samriddhi_yojana', 'unit_linked_insurance_premium')
    def onchange_function_80c(self):
        self.total_declared_80c = self.employee_provident_fund + self.five_year_fixed_deposite + self.children_tution_fees + self.contribution_to_pension_fund + self.deposite_in_nsc + self.deposite_in_nss + self.deposite_in_post_office + self.equity_linked_saving_scheme + self.interest_on_nsc + self.kisan_vikas_patra + self.life_insurance_premium + self.long_term_infrastructure_bond + self.mutual_funds + self.nabard_rural_funds + self.national_pension_scheme + self.nhb_scheme + self.post_office_time_deposite + self.pradhan_mantri_suraksha_bima + self.public_provident_fund + self.repayment_of_housing_loan + self.stamp_duty_registration_charges + self.sukanya_samriddhi_yojana + self.unit_linked_insurance_premium
        self.applicable_declared_80c = self.total_declared_80c

        if self.total_declared_80c > 150000:
            self.applicable_declared_80c = 150000
        else:
            self.total_declared_80c

    # Other Chapter VI-A Deductions
    #section_24b = fields.Integer(string="section 24(b)", tracking=True)
    additional_interest_on_housing_2016 = fields.Integer(
        string="80EE Additional Interest on housing loan borrowed as on 1st Apr 2016", tracking=True)
    additional_interest_on_housing_2019 = fields.Integer(
        string="80EEA Additional Interest on Housing loan borrowed as on 1st Apr 2019", tracking=True,
        help="For first-time home buyers.")
    interest_on_electric_vehicle = fields.Integer(
        string="80EEB Interest on Electric Vehicle borrowed as on 1st Apr 2019", tracking=True)
    contribution_to_nps = fields.Integer(string="80CCD1(B) Contribution to NPS 2015", tracking=True)
    interest_on_savings_etc = fields.Integer(
        string="80TTB Interest on Deposits in Savings Account, FDs, Post Office And Cooperative Society for Senior Citizen",
        tracking=True)
    superannuation_exemption = fields.Integer(string="10(13) Superannuation Exemption", tracking=True)
    donation_100_exemption = fields.Integer(string="80G Donation - 100 Percent Exemption", tracking=True)
    donation_50_exemption = fields.Integer(string="80G Donation - 50 Percent Exemption", tracking=True)
    donation_children_education = fields.Integer(string="80G Donation - Children Education", tracking=True)
    donation_political_parties = fields.Integer(string="80G Donation - Political Parties", tracking=True)
    interests_on_deposites = fields.Integer(
        string="80TTA Interest on Deposits in Savings Account, FDs, Post Office And Cooperative Society", tracking=True)
    interests_on_loan_self_higher = fields.Integer(string="80E Interest on Loan of higher Self education",
                                                   tracking=True)
    medical_insurance_for_handicapped = fields.Integer(
        string="80DD Medical Treatment / Insurance of handicapped Dependant", tracking=True)
    medical_insurance_for_handicapped_severe = fields.Integer(
        string="80DD Medical Treatment / Insurance of handicapped Dependant (Severe)", tracking=True)
    medical_insurance_specified_disease_only = fields.Integer(
        string="80DDB Medical Treatment ( Specified Disease only )", tracking=True)
    medical_insurance_specified_disease_only_senior_citizen = fields.Integer(
        string="80DDB Medical Treatment (Specified Disease only)- Senior Citizen", tracking=True)
    permanent_physical_disability_above_80 = fields.Integer(
        string="80U Permanent Physical Disability (Above 80 percent)", tracking=True)
    permanent_physical_disability_40_80 = fields.Integer(
        string="80U Permanent Physical Disability (Between 40 - 80 Percent)", tracking=True)
    rajiv_gandhi_equity_scheme = fields.Integer(string="80CCG Rajiv Gandhi Equity Scheme", tracking=True)
    total_declared_vi_a_deductions = fields.Integer(compute="onchange_function_deduction", string="Total declared in ?",
                                                    tracking=True)
    applicable_declared_vi_a_deductions = fields.Integer(string="Applicable amount declared in ?", tracking=True)

    @api.onchange('additional_interest_on_housing_2016', 'additional_interest_on_housing_2019',
                  'interest_on_electric_vehicle', 'contribution_to_nps', 'interest_on_savings_etc',
                  'superannuation_exemption', 'donation_100_exemption', 'donation_50_exemption',
                  'donation_children_education', 'donation_political_parties', 'interests_on_deposites',
                  'interests_on_loan_self_higher', 'medical_insurance_for_handicapped',
                  'medical_insurance_for_handicapped_severe', 'medical_insurance_specified_disease_only',
                  'medical_insurance_specified_disease_only_senior_citizen', 'permanent_physical_disability_above_80',
                  'permanent_physical_disability_40_80', 'rajiv_gandhi_equity_scheme')
    def onchange_function_deduction(self):

        # section_24b = 0
        # if self.section_24b > 200000:
        #     section_24b = 200000
        # else:
        #     section_24b = self.section_24b
        # additional_interest_on_housing_2016 = 0

        if self.additional_interest_on_housing_2016 > 50000:
            additional_interest_on_housing_2016 = 50000
        else:
            additional_interest_on_housing_2016 = self.additional_interest_on_housing_2016

        additional_interest_on_housing_2019 = 0
        if self.additional_interest_on_housing_2019 > 150000:
            additional_interest_on_housing_2019 = 150000
        else:
            additional_interest_on_housing_2019 = self.additional_interest_on_housing_2019

        interest_on_electric_vehicle = 0
        if self.interest_on_electric_vehicle > 150000:
            interest_on_electric_vehicle = 150000
        else:
            interest_on_electric_vehicle = self.interest_on_electric_vehicle

        contribution_to_nps = 0
        if self.contribution_to_nps > 50000:
            contribution_to_nps = 50000
        else:
            contribution_to_nps = self.contribution_to_nps

        interest_on_savings_etc = 0
        if self.interest_on_savings_etc > 50000:
            interest_on_savings_etc = 50000
        else:
            interest_on_savings_etc = self.interest_on_savings_etc

        superannuation_exemption = 0
        if self.superannuation_exemption > 150000:
            superannuation_exemption = 150000
        else:
            superannuation_exemption = self.superannuation_exemption

        donation_100_exemption = 0
        if self.donation_100_exemption > 99999999:
            donation_100_exemption = 99999999
        else:
            donation_100_exemption = self.donation_100_exemption

        donation_50_exemption = 0
        if self.donation_50_exemption > 99999999:
            donation_50_exemption = 99999999
        else:
            donation_50_exemption = self.donation_50_exemption

        donation_children_education = 0
        if self.donation_children_education > 99999999:
            donation_children_education = 99999999
        else:
            donation_children_education = self.donation_children_education

        donation_political_parties = 0
        if self.donation_political_parties > 99999999:
            donation_political_parties = 99999999
        else:
            donation_political_parties = self.donation_political_parties

        interests_on_deposites = 0
        if self.interests_on_deposites > 10000:
            interests_on_deposites = 10000
        else:
            interests_on_deposites = self.interests_on_deposites

        interests_on_loan_self_higher = 0
        if self.interests_on_loan_self_higher > 99999999:
            interests_on_loan_self_higher = 99999999
        else:
            interests_on_loan_self_higher = self.interests_on_loan_self_higher

        medical_insurance_for_handicapped = 0
        if self.medical_insurance_for_handicapped > 75000:
            medical_insurance_for_handicapped = 75000
        else:
            medical_insurance_for_handicapped = self.medical_insurance_for_handicapped

        medical_insurance_for_handicapped_severe = 0
        if self.medical_insurance_for_handicapped_severe > 125000:
            medical_insurance_for_handicapped_severe = 125000
        else:
            medical_insurance_for_handicapped_severe = self.medical_insurance_for_handicapped_severe

        medical_insurance_specified_disease_only = 0
        if self.medical_insurance_specified_disease_only > 40000:
            medical_insurance_specified_disease_only = 40000
        else:
            medical_insurance_specified_disease_only = self.medical_insurance_specified_disease_only

        medical_insurance_specified_disease_only_senior_citizen = 0
        if self.medical_insurance_specified_disease_only_senior_citizen > 100000:
            medical_insurance_specified_disease_only_senior_citizen = 100000
        else:
            medical_insurance_specified_disease_only_senior_citizen = self.medical_insurance_specified_disease_only_senior_citizen

        permanent_physical_disability_above_80 = 0
        if self.permanent_physical_disability_above_80 > 125000:
            permanent_physical_disability_above_80 = 125000
        else:
            permanent_physical_disability_above_80 = self.permanent_physical_disability_above_80

        permanent_physical_disability_40_80 = 0
        if self.permanent_physical_disability_40_80 > 75000:
            permanent_physical_disability_40_80 = 75000
        else:
            permanent_physical_disability_40_80 = self.permanent_physical_disability_40_80

        rajiv_gandhi_equity_scheme = 0
        if self.rajiv_gandhi_equity_scheme > 25000:
            rajiv_gandhi_equity_scheme = 25000
        else:
            rajiv_gandhi_equity_scheme = self.rajiv_gandhi_equity_scheme

        self.total_declared_vi_a_deductions = self.additional_interest_on_housing_2016 + self.additional_interest_on_housing_2019 + self.interest_on_electric_vehicle + self.contribution_to_nps + self.interest_on_savings_etc + self.superannuation_exemption + self.donation_100_exemption + self.donation_50_exemption + self.donation_children_education + self.donation_political_parties + self.interests_on_deposites + self.interests_on_loan_self_higher + self.medical_insurance_for_handicapped + self.medical_insurance_for_handicapped_severe + self.medical_insurance_specified_disease_only + self.medical_insurance_specified_disease_only_senior_citizen + self.permanent_physical_disability_above_80 + self.permanent_physical_disability_40_80 + self.rajiv_gandhi_equity_scheme
        self.applicable_declared_vi_a_deductions = additional_interest_on_housing_2016 + additional_interest_on_housing_2019 + interest_on_electric_vehicle + contribution_to_nps + interest_on_savings_etc + superannuation_exemption + donation_100_exemption + donation_50_exemption + donation_children_education + donation_political_parties + interests_on_deposites + interests_on_loan_self_higher + medical_insurance_for_handicapped + medical_insurance_for_handicapped_severe + medical_insurance_specified_disease_only + medical_insurance_specified_disease_only_senior_citizen + permanent_physical_disability_above_80 + permanent_physical_disability_40_80 + rajiv_gandhi_equity_scheme

        # House Rent

    house_allowance_ids = fields.One2many('homerent.allowance', 'it_declaration_id', string="House Rent")
    total_declared_hra = fields.Integer(compute="onchange_function_hra", string="Total declared in ?", tracking=True)

    @api.onchange(house_allowance_ids)
    def onchange_function_hra(self):
        annual_rent = 0
        total = 0
        for annual_rent in self.house_allowance_ids:
            total += annual_rent.annual_rent_amount
        self.total_declared_hra = total

    # Medical (Sec 80D)
    declared_amount_1 = fields.Integer(string="80D Preventive Health Checkup - Dependant Parents", tracking=True)
    declared_amount_2 = fields.Integer(string="80D Medical Bills - Senior Citizen", tracking=True)
    declared_amount_3 = fields.Integer(string="80D Medical Insurance Premium", tracking=True)
    declared_amount_4 = fields.Integer(string="80D Medical Insurance Premium - Dependant Parents", tracking=True)
    declared_amount_5 = fields.Integer(string="80D Preventive Health Check-up", tracking=True)
    age = fields.Selection([
        ("< 60", "< 60"),
        ("60 - 79", "60 - 79"),
        (">= 80", ">= 80"),
    ],
        tracking=True,
        string="Age", compute="_compute_age"
    )
    age_dependant = fields.Selection([
        ("< 60", "< 60"),
        ("60 - 79", "60 - 79"),
        (">= 80", ">= 80"),
    ],
        tracking=True,
        string="Age"
    )

    @api.depends('employee_id.birthday')
    def _compute_age(self):
        for record in self:
            dob = record.employee_id.birthday
            if dob:
                today = date.today()
                years = today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))

                if years < 60:
                    record.age = "< 60"
                elif 60 <= years < 80:
                    record.age = "60 - 79"
                else:
                    record.age = ">= 80"
            else:
                record.age = False

    @api.onchange('age', 'age_dependant')
    def _onchange_age_dependant(self):
        for rec in self:
            # Correct logic with proper parentheses
            if rec.age in ["60 - 79", ">= 80"] and rec.age_dependant == "< 60":
                rec.age_dependant = False
                return {
                    'warning': {
                        'title': "Validation Error",
                        'message': "Your father's age is below your age. Please enter a valid age."

                    }
                }


    total_declared_medical = fields.Integer(compute="onchange_function_medical", string="Total declared in ?",
                                            tracking=True)
    applicable_declared_medical = fields.Integer(string="Applicable Amount in ?", tracking=True)

    @api.onchange('declared_amount_1', 'declared_amount_2', 'declared_amount_3', 'declared_amount_4',
                  'declared_amount_5')
    def onchange_function_medical(self):

        declared_amount_1 = 0
        if self.declared_amount_1 > 5000:
            declared_amount_1 = 5000
        else:
            declared_amount_1 = self.declared_amount_1

        declared_amount_2 = 0
        if self.declared_amount_2 > 50000:
            declared_amount_2 = 50000
        else:
            declared_amount_2 = self.declared_amount_2

        declared_amount_3 = 0
        if self.declared_amount_3 > 25000:
            declared_amount_3 = 25000
        else:
            declared_amount_3 = self.declared_amount_3

        declared_amount_4 = 0
        if self.declared_amount_4 > 50000:
            declared_amount_4 = 50000
        else:
            declared_amount_4 = self.declared_amount_4

        declared_amount_5 = 0
        if self.declared_amount_5 > 5000:
            declared_amount_5 = 5000
        else:
            declared_amount_5 = self.declared_amount_5

        self.total_declared_medical = self.declared_amount_1 + self.declared_amount_2 + self.declared_amount_3 + self.declared_amount_4 + self.declared_amount_5
        #self.applicable_declared_medical = declared_amount_1 + declared_amount_2 + declared_amount_3 + declared_amount_4 + declared_amount_5

        if not self.age and not self.age_dependant:
            self.applicable_declared_medical = 0
        elif self.age == "< 60":
            if not self.age_dependant:
                self.applicable_declared_medical = 25000
            elif self.age_dependant == "< 60":
                self.applicable_declared_medical = 50000
            elif self.age_dependant in ("60 - 79", ">= 80"):
                self.applicable_declared_medical = 75000
        else:
            if not self.age_dependant:
                self.applicable_declared_medical = 50000
            else:
                self.applicable_declared_medical = 100000

        if self.total_declared_medical < self.applicable_declared_medical:
            self.applicable_declared_medical = self.total_declared_medical


    # Income/loss from House Property
    income_loss_ids = fields.One2many('income.loss', 'it_declaration_id', string="Income/Loss From House Property")
    interest_on_housing_loan = fields.Integer(string="Interest on Housing Loan (Self Occupied) in ?", tracking=True)
    lender_self_name = fields.Char(string="Lenders Name", tracking=True)
    lender_self_pan = fields.Char(string="Lenders PAN", tracking=True)
    total_income_loss = fields.Integer(compute="onchange_function_total",
                                       string="Total Income/Loss from Let Out Property", tracking=True)
    total_exemption = fields.Integer(compute="onchange_function_exemption", string="Total Exemption in ?",
                                     tracking=True)

    @api.onchange('income_loss_ids')
    def onchange_function_total(self):
        total = 0
        grand_total = 0
        for total in self.income_loss_ids:
            grand_total += total.income_loss_let_out
        self.total_income_loss = grand_total

    @api.onchange('income_loss_ids', 'interest_on_housing_loan', 'total_income_loss')
    def onchange_function_exemption(self):
        if (-self.interest_on_housing_loan + self.total_income_loss) <= -200000:
            self.total_exemption = -200000
        else:
            self.total_exemption = -self.interest_on_housing_loan + self.total_income_loss

            # Other Income

    other_income_ids = fields.One2many('other.income', 'it_declaration_id', string="Other Income")
    total_declared_other = fields.Integer(compute="onchange_function_other", string="Total declared in ?",
                                          tracking=True)

    @api.onchange('other_income_ids')
    def onchange_function_other(self):
        other = 0
        other_total = 0
        for other in self.other_income_ids:
            other_total += other.declared_amount
        self.total_declared_other = other_total

    # Income From Previous Employer
    income_after_exemptions = fields.Integer(string="Income after Exemptions", tracking=True)
    professional_tax = fields.Integer(string="Profession Tax - PT", tracking=True)
    provident_fund = fields.Integer(string="Provident Fund - PF", tracking=True)
    tax_on_income = fields.Integer(string="Tax On Income", tracking=True)
    surcharge = fields.Integer(string="Surcharge", tracking=True)
    education_cess = fields.Integer(string="Education Cess", tracking=True)
    total_tax_previous_employer = fields.Integer(compute="depends_function_previous", string="Total Tax in ?",
                                                 help="Total Tax = Tax On Income + Surcharge + Education Cess",
                                                 tracking=True)

    @api.depends('tax_on_income', 'surcharge', 'education_cess')
    def depends_function_previous(self):
        self.total_tax_previous_employer = self.tax_on_income - self.surcharge - self.education_cess

    @api.onchange('applicable_declared_80c', 'applicable_declared_vi_a_deductions', 'total_declared_hra',
                  'applicable_declared_medical', 'total_exemption', 'total_declared_other',
                  'total_tax_previous_employer')
    def onchange_total_calculation(self):
        self.grand_total = self.applicable_declared_80c + self.applicable_declared_vi_a_deductions + self.total_declared_hra + self.applicable_declared_medical + self.total_exemption + self.total_declared_other + self.total_tax_previous_employer

    def grand_amount(self):
        grand_amount = {
            '80c': self.applicable_declared_80c,
            '80ccd': self.contribution_to_nps,
            '80d': self.applicable_declared_medical,
            '80other': self.applicable_declared_vi_a_deductions - self.contribution_to_nps,
            'house_rent': self.total_declared_hra,
            'income_lose_house_property': self.total_exemption,
            'income_lose_house_property_new': self.total_income_loss,
            'other_income': self.total_declared_other,
            'income_previous_employer': self.total_tax_previous_employer,
            'previous_employer_professional_tax': self.professional_tax,
            'previous_employer_pf_employer': self.provident_fund,
            'regime': self.tax_regime,
            'gratuity_from_previous_system': self.gratuity_from_previous_system,
            'tax_on_income': self.tax_on_income,
            'surcharge': self.surcharge,
            'ecess': self.education_cess
        }
        return grand_amount

    def lock(self):
        for self in self:
            self.write({'status': 'locked'})

    def unlock(self):
        for self in self:
            self.write({'status': 'unlocked'})

    def submit(self):
        self.write({'status': 'submitted'})

    def write(self, vals):
        is_editable = True
        computed_fields = ['total_declared_80c', 'grand_total', 'applicable_declared_80c',
                           'applicable_declared_vi_a_deductions', 'applicable_declared_medical', 'status']
        for key in vals:
            is_editable = True if key in computed_fields or self.status == 'unlocked' else False
        if is_editable:
            super(ItDeclarationPayslip, self).write(vals)
        else:
            raise ValidationError(
                'IT declaration can only be updated when it is unlocked. Please contact accountant in case you want to make some changes.')


class HomerentAllowance(models.Model):
    _name = 'homerent.allowance'
    _description = 'House Rent'

    it_declaration_id = fields.Many2one('it.declaration.payslip', string="House Rent")
    from_possession = fields.Date(string="From", tracking=True)
    to_possession = fields.Date(string="To", tracking=True)
    monthly_rent_amount = fields.Integer(string="Monthly Rent Amount", tracking=True)
    annual_rent_amount = fields.Integer(compute="depends_function_annual_rent", string="Annual Rent Amount",
                                        tracking=True, help="If annual rent is more than 1 Lakh Then You Have to Give "
                                                            "Landlord's PAN")
    house_name_number = fields.Char(string="House Name/Number", tracking=True)
    street_area_locality = fields.Char(string="Street/Area/Locality", tracking=True)
    town_city = fields.Char(string="Town/City", tracking=True)
    state = fields.Char(string="State", tracking=True)
    country = fields.Char(string="Country", tracking=True)
    pin_code = fields.Integer(string="Pincode", tracking=True)
    pan_info_landlord = fields.Selection([
        ("yes", "Yes"),
        ("no", "No"),
    ],
        tracking=True, readonly=True
    )
    landlord_name = fields.Char(string="Landlord's Name", tracking=True)
    landlord_pan = fields.Char(string="Landlord's PAN", tracking=True)
    landlord_house_name_number = fields.Char(string="House Name/Number", tracking=True)
    landlord_street_area = fields.Char(string="Street/Area/Locality", tracking=True)
    landlord_town_city = fields.Char(string="Town/City", tracking=True)
    landlord_pincode = fields.Char(string="Pincode", tracking=True)
    agreement = fields.Binary(string="Upload Rent Agreement")

    @api.onchange('monthly_rent_amount', 'from_possession', 'to_possession')
    def depends_function_annual_rent(self):
        for rent in self:
            if rent.from_possession and rent.to_possession:
                today = date.today()
                fy_start = date(today.year if today.month >= 4 else today.year - 1, 4, 1)
                fy_end = date(fy_start.year + 1, 3, 31)

                # Adjust the possession period to the financial year
                overlap_start = max(rent.from_possession, fy_start)
                overlap_end = min(rent.to_possession, fy_end)

                if overlap_start <= overlap_end:
                    delta = relativedelta(overlap_end, overlap_start)
                    months = delta.years * 12 + delta.months + 1  # +1 to include both start and end month
                    rent.annual_rent_amount = rent.monthly_rent_amount * months
                else:
                    rent.annual_rent_amount = 0  # No overlap with financial year
            else:
                rent.annual_rent_amount = 0

            rent.pan_info_landlord = 'yes' if rent.annual_rent_amount > 100000 else 'no'


class IncomeLoss(models.Model):
    _name = 'income.loss'
    _description = 'Income or Loss From House Property'

    it_declaration_id = fields.Many2one('it.declaration.payslip', string="Income/Loss From House Property")
    annual_letable_received = fields.Integer(string="Annual Letable Value/Rent Received or Receivable", tracking=True)
    munciple_tax_paid = fields.Integer(string="Less: Municipal Taxes Paid During the Year", tracking=True)
    unreleased_rent = fields.Integer(string="Less: Unrealized Rent", tracking=True)
    tax_on_income = fields.Integer(compute="depends_function_net_value", string="NET VALUE IN ?", tracking=True)
    standard_deduction = fields.Integer(compute="depends_function_standard_deduction",
                                        string="Standard Deduction at 30 Percent of Net Annual Value", tracking=True)
    interest_housing_loan = fields.Integer(string="Interest on Housing Loan", tracking=True)
    lender_name = fields.Char(string="Lenders Name", tracking=True)
    lender_pan = fields.Char(string="Lenders PAN", tracking=True)
    income_loss_let_out = fields.Integer(compute="depends_function_income", string="Income/Loss from Let Out Property",
                                         tracking=True)

    @api.depends('annual_letable_received', 'munciple_tax_paid', 'unreleased_rent')
    def depends_function_net_value(self):
        for rent in self:
            rent.tax_on_income = rent.annual_letable_received - (rent.munciple_tax_paid + rent.unreleased_rent)

    @api.depends('tax_on_income')
    def depends_function_standard_deduction(self):
        for deduction in self:
            deduction.standard_deduction = deduction.tax_on_income * 0.30

    @api.depends('tax_on_income', 'standard_deduction', 'interest_housing_loan')
    def depends_function_income(self):
        for income in self:
            income.income_loss_let_out = income.tax_on_income - income.standard_deduction - income.interest_housing_loan


class OtherIncome(models.Model):
    _name = 'other.income'
    _description = 'Other Income'

    it_declaration_id = fields.Many2one('it.declaration.payslip', string="Other Income")
    particulars = fields.Char(string="Particulars")
    declared_amount = fields.Integer(string="Declared Amount")
