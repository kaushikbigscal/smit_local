/** @odoo-module **/

import { Component } from '@odoo/owl';
import { registry } from '@web/core/registry';
import { useService } from '@web/core/utils/hooks';
import { onMounted, useRef, xml, onWillUnmount } from '@odoo/owl';

export class CustomListController extends Component {
    static template = xml`<t t-call="monthly_attendance_report.CustomListView"/>`;

    setup() {
        this.actionService = useService('action');
        this.orm = useService('orm');
        this.notification = useService('notification');

        // Refs for template elements
        this.treeViewContainerRef = useRef('tree_view_container');
        this.reportDataContainerRef = useRef('report_data_container_ref');
        this.monthFilterInputRef = useRef('month_filter_input');
        this.departmentFilterInputRef = useRef('department_filter_input');
        this.employeeFilterInputRef = useRef('employee_filter_input');
        this.departmentInputRef = useRef('department_input');
        this.employeeInputRef = useRef('employee_input');
        this.departmentTagsRef = useRef('department_tags');
        this.employeeTagsRef = useRef('employee_tags');
        this.viewReportButtonRef = useRef('view_report_button');
        this.downloadReportButtonRef = useRef('download_report_button');

        // State
        this.selectedDepartments = new Set();
        this.selectedEmployees = new Set();
        this.allDepartments = [];
        this.allEmployees = [];
        this.reportLines = [];
        this.isDepartmentDropdownVisible = false;
        this.isEmployeeDropdownVisible = false;
        this.isAllDepartmentsSelected = true;
        this.isAllEmployeesSelected = true;
        this.isDestroying = false;

        onMounted(() => {
            this._setDefaultMonth();
            this._populateDropdowns();
            this._updateDepartmentTags();
            this._updateEmployeeTags();
        });

        this._onGlobalClick = (ev) => {
            if (this.isDestroying) return;
            // Department dropdown
            if (this.isDepartmentDropdownVisible) {
                const depInput = this.departmentInputRef.el;
                const depContainer = this.departmentFilterInputRef.el;
                const depDropdown = depContainer && depContainer.querySelector('.o_dropdown_menu');
                const depInputDropdown = depInput && depInput.closest('.o_input_dropdown');
                const isClickOutside = depContainer && !depContainer.contains(ev.target) &&
                    (!depInputDropdown || !depInputDropdown.contains(ev.target)) &&
                    (!depDropdown || !depDropdown.contains(ev.target)) &&
                    !(ev.target.classList && ev.target.classList.contains('badge'));
                if (isClickOutside) {
                    this.isDepartmentDropdownVisible = false;
                    this._hideDepartmentDropdown();
                }
            }
            // Employee dropdown
            if (this.isEmployeeDropdownVisible) {
                const empInput = this.employeeInputRef.el;
                const empContainer = this.employeeFilterInputRef.el;
                const empDropdown = empContainer && empContainer.querySelector('.o_dropdown_menu');
                const empInputDropdown = empInput && empInput.closest('.o_input_dropdown');
                const isClickOutside = empContainer && !empContainer.contains(ev.target) &&
                    (!empInputDropdown || !empInputDropdown.contains(ev.target)) &&
                    (!empDropdown || !empDropdown.contains(ev.target)) &&
                    !(ev.target.classList && ev.target.classList.contains('badge'));
                if (isClickOutside) {
                    this.isEmployeeDropdownVisible = false;
                    this._hideEmployeeDropdown();
                }
            }
        };
        document.addEventListener('click', this._onGlobalClick, true);

        onWillUnmount(() => {
            this.isDestroying = true;
            document.removeEventListener('click', this._onGlobalClick, true);
        });
    }

    _setDefaultMonth() {
        const monthInput = this.monthFilterInputRef.el;
        if (monthInput) {
            const today = new Date();
            const year = today.getFullYear();
            const month = String(today.getMonth() + 1).padStart(2, '0');
            const currentMonth = `${year}-${month}`;
            monthInput.value = currentMonth;
        }
    }

    async _populateDropdowns() {
        try {
            this.allDepartments = await this.orm.searchRead('hr.department', [], ['name']);
            this.allEmployees = await this.orm.searchRead('hr.employee', [], ['name', 'department_id']);

            if (this.departmentFilterInputRef.el) {
                this.departmentFilterInputRef.el.addEventListener('click', (ev) => {
                    if (!ev.target.classList.contains('o_delete')) {
                        this.isDepartmentDropdownVisible = true;
                        this._showDepartmentDropdown();
                    }
                });
                this.departmentFilterInputRef.el.addEventListener('input', (ev) => this._onDepartmentInput(ev));
            }

            if (this.employeeFilterInputRef.el) {
                this.employeeFilterInputRef.el.addEventListener('click', (ev) => {
                    if (!ev.target.classList.contains('o_delete')) {
                        this.isEmployeeDropdownVisible = true;
                        this._showEmployeeDropdown();
                    }
                });
                this.employeeFilterInputRef.el.addEventListener('input', (ev) => this._onEmployeeInput(ev));
            }

        } catch (error) {
            console.error('Error populating dropdowns:', error);
            this.notification.add('Error loading dropdown data', { type: 'danger' });
        }
    }

    _onDepartmentInput(ev) {
        if (!this.departmentFilterInputRef.el) return;
        const searchTerm = ev.target.value.toLowerCase();
        const filteredDepts = this.allDepartments.filter(dept =>
            dept.name.toLowerCase().includes(searchTerm) &&
            !this.selectedDepartments.has(dept.id)
        );
        this._showDepartmentDropdown(filteredDepts);
    }

    _onEmployeeInput(ev) {
        if (!this.employeeFilterInputRef.el) return;
        const searchTerm = ev.target.value.toLowerCase();
        const filteredEmps = this.allEmployees.filter(emp =>
            emp.name.toLowerCase().includes(searchTerm) &&
            !this.selectedEmployees.has(emp.id) &&
            (this.selectedDepartments.size === 0 ||
                this.selectedDepartments.has(emp.department_id[0]))
        );
        this._showEmployeeDropdown(filteredEmps);
    }

    _showDepartmentDropdown(departments = this.allDepartments) {
        if (!this.departmentFilterInputRef.el || !this.isDepartmentDropdownVisible) return;
        let dropdown = this.departmentFilterInputRef.el.querySelector('.o_dropdown_menu');
        if (!dropdown) {
            dropdown = document.createElement('div');
            dropdown.className = 'o_dropdown_menu';
            this.departmentFilterInputRef.el.appendChild(dropdown);
        }

        // Show "All Departments" option when there are selections OR when nothing is selected
        const showAllOption = this.selectedDepartments.size > 0 || !this.isAllDepartmentsSelected;

        dropdown.innerHTML =
            (showAllOption ? `<div class="o_dropdown_item ${this.isAllDepartmentsSelected ? 'active' : ''}" data-id="all">All Departments</div>` : '') +
            departments.map(dept => `
                <div class="o_dropdown_item ${this.selectedDepartments.has(dept.id) ? 'active' : ''}" data-id="${dept.id}">
                    ${dept.name}
                </div>
            `).join('');
        dropdown.style.display = 'block';
        dropdown.querySelectorAll('.o_dropdown_item').forEach(item => {
            item.addEventListener('click', (ev) => {
                ev.stopPropagation();
                if (item.dataset.id === 'all') {
                    this._selectAllDepartments();
                } else {
                    this._selectDepartment(item.dataset.id, item.textContent.trim());
                }
            });
        });
    }

    _showEmployeeDropdown(employees = this.allEmployees) {
        if (!this.employeeFilterInputRef.el || !this.isEmployeeDropdownVisible) return;
        let dropdown = this.employeeFilterInputRef.el.querySelector('.o_dropdown_menu');
        if (!dropdown) {
            dropdown = document.createElement('div');
            dropdown.className = 'o_dropdown_menu';
            this.employeeFilterInputRef.el.appendChild(dropdown);
        }
        const filteredEmployees = this.selectedDepartments.size > 0 && !this.isAllDepartmentsSelected
            ? employees.filter(emp => this.selectedDepartments.has(emp.department_id[0]))
            : employees;

        // Show "All Employees" option when there are selections OR when nothing is selected
        const showAllOption = this.selectedEmployees.size > 0 || !this.isAllEmployeesSelected;

        dropdown.innerHTML =
            (showAllOption ? `<div class="o_dropdown_item ${this.isAllEmployeesSelected ? 'active' : ''}" data-id="all">All Employees</div>` : '') +
            filteredEmployees.map(emp => `
                <div class="o_dropdown_item ${this.selectedEmployees.has(emp.id) ? 'active' : ''}" data-id="${emp.id}">
                    ${emp.name}
                </div>
            `).join('');
        dropdown.style.display = 'block';
        dropdown.querySelectorAll('.o_dropdown_item').forEach(item => {
            item.addEventListener('click', (ev) => {
                ev.stopPropagation();
                if (item.dataset.id === 'all') {
                    this._selectAllEmployees();
                } else {
                    this._selectEmployee(item.dataset.id, item.textContent.trim());
                }
            });
        });
    }

    _hideDepartmentDropdown() {
        if (!this.departmentFilterInputRef.el) return;
        const dropdown = this.departmentFilterInputRef.el.querySelector('.o_dropdown_menu');
        if (dropdown) {
            dropdown.style.display = 'none';
        }
    }

    _hideEmployeeDropdown() {
        if (!this.employeeFilterInputRef.el) return;
        const dropdown = this.employeeFilterInputRef.el.querySelector('.o_dropdown_menu');
        if (dropdown) {
            dropdown.style.display = 'none';
        }
    }

    _selectAllDepartments() {
        this.selectedDepartments.clear();
        this.isAllDepartmentsSelected = true;
        this._updateDepartmentTags();
        if (this.departmentInputRef.el) {
            this.departmentInputRef.el.value = '';
        }
        this._hideDepartmentDropdown();
        this._selectAllEmployees();
    }

    _selectAllEmployees() {
        this.selectedEmployees.clear();
        this.isAllEmployeesSelected = true;
        this._updateEmployeeTags();
        if (this.employeeInputRef.el) {
            this.employeeInputRef.el.value = '';
        }
        this._hideEmployeeDropdown();
    }

    _selectDepartment(id, name) {
        this.isAllDepartmentsSelected = false;
        this.selectedDepartments.add(parseInt(id));
        this._updateDepartmentTags();
        if (this.departmentInputRef.el) {
            this.departmentInputRef.el.value = '';
        }
        this._hideDepartmentDropdown();
        this._updateEmployeeDropdownData();
    }

    _selectEmployee(id, name) {
        this.isAllEmployeesSelected = false;
        this.selectedEmployees.add(parseInt(id));
        this._updateEmployeeTags();
        if (this.employeeInputRef.el) {
            this.employeeInputRef.el.value = '';
        }
        this._hideEmployeeDropdown();
    }

    _updateDepartmentTags() {
        if (!this.departmentTagsRef.el || !this.departmentInputRef.el) return;

        const inputDropdown = this.departmentInputRef.el.closest('.o_input_dropdown');
        if (inputDropdown) {
            const existingAllBadge = inputDropdown.querySelector('.badge[data-id="all"]');
            if (existingAllBadge) existingAllBadge.remove();
        }

        if (this.selectedDepartments.size === 0 && this.isAllDepartmentsSelected) {
            // Show "All Departments" badge in the input area
            this.departmentTagsRef.el.innerHTML = '';
            if (inputDropdown) {
                const allBadge = document.createElement('span');
                allBadge.className = 'badge badge-info';
                allBadge.setAttribute('data-id', 'all');
                allBadge.innerHTML = `All Departments <span class="o_delete">×</span>`;

                // Add delete functionality for "All Departments" badge
                allBadge.querySelector('.o_delete').addEventListener('click', (ev) => {
                    ev.stopPropagation();
                    this.isAllDepartmentsSelected = false;
                    allBadge.remove();
                    if (this.departmentInputRef.el) {
                        this.departmentInputRef.el.placeholder = 'Select Departments...';
                    }
                    // Reset employees when departments change
                    this._selectAllEmployees();
                });

                inputDropdown.insertBefore(allBadge, this.departmentInputRef.el);
            }
            if (this.departmentInputRef.el) {
                this.departmentInputRef.el.placeholder = '';
            }
        } else if (this.selectedDepartments.size > 0) {
            // Show selected department badges
            this.departmentTagsRef.el.innerHTML = Array.from(this.selectedDepartments).map(id => {
                const dept = this.allDepartments.find(d => d.id === id);
                return `
                    <span class="badge badge-info" data-id="${id}">
                        ${dept.name}
                        <span class="o_delete">×</span>
                    </span>
                `;
            }).join('');
            if (this.departmentInputRef.el) {
                this.departmentInputRef.el.placeholder = '';
            }
            this.isAllDepartmentsSelected = false;
            this.departmentTagsRef.el.querySelectorAll('.o_delete').forEach(deleteBtn => {
                deleteBtn.addEventListener('click', (ev) => {
                    ev.stopPropagation();
                    const badge = ev.target.closest('.badge');
                    const id = badge.dataset.id;
                    this.selectedDepartments.delete(parseInt(id));
                    // Remove employees whose department is no longer selected
                    this.selectedEmployees = new Set(Array.from(this.selectedEmployees).filter(empId => {
                        const emp = this.allEmployees.find(e => e.id === empId);
                        return emp && this.selectedDepartments.has(emp.department_id[0]);
                    }));
                    this._updateDepartmentTags();
                    this._updateEmployeeTags();
                });
            });
        } else {
            // No departments selected and not "All" - show placeholder
            this.departmentTagsRef.el.innerHTML = '';
            if (this.departmentInputRef.el) {
                this.departmentInputRef.el.placeholder = 'Select Departments...';
            }
        }
    }

    _updateEmployeeTags() {
        if (!this.employeeTagsRef.el || !this.employeeInputRef.el) return;

        const inputDropdown = this.employeeInputRef.el.closest('.o_input_dropdown');
        if (inputDropdown) {
            const existingAllBadge = inputDropdown.querySelector('.badge[data-id="emp-all"]');
            if (existingAllBadge) existingAllBadge.remove();
        }

        if (this.selectedEmployees.size === 0 && this.isAllEmployeesSelected) {
            // Show "All Employees" badge in the input area
            this.employeeTagsRef.el.innerHTML = '';
            if (inputDropdown) {
                const allBadge = document.createElement('span');
                allBadge.className = 'badge badge-info';
                allBadge.setAttribute('data-id', 'emp-all');
                allBadge.innerHTML = `All Employees <span class="o_delete">×</span>`;

                // Add delete functionality for "All Employees" badge
                allBadge.querySelector('.o_delete').addEventListener('click', (ev) => {
                    ev.stopPropagation();
                    this.isAllEmployeesSelected = false;
                    allBadge.remove();
                    if (this.employeeInputRef.el) {
                        this.employeeInputRef.el.placeholder = 'Select Employees...';
                    }
                });

                inputDropdown.insertBefore(allBadge, this.employeeInputRef.el);
            }
            if (this.employeeInputRef.el) {
                this.employeeInputRef.el.placeholder = '';
            }
        } else if (this.selectedEmployees.size > 0) {
            // Show selected employee badges
            this.employeeTagsRef.el.innerHTML = Array.from(this.selectedEmployees).map(id => {
                const emp = this.allEmployees.find(e => e.id === id);
                return `
                    <span class="badge badge-info" data-id="${id}">
                        ${emp.name}
                        <span class="o_delete">×</span>
                    </span>
                `;
            }).join('');
            if (this.employeeInputRef.el) {
                this.employeeInputRef.el.placeholder = '';
            }
            this.isAllEmployeesSelected = false;
            this.employeeTagsRef.el.querySelectorAll('.o_delete').forEach(deleteBtn => {
                deleteBtn.addEventListener('click', (ev) => {
                    ev.stopPropagation();
                    const badge = ev.target.closest('.badge');
                    const id = badge.dataset.id;
                    this.selectedEmployees.delete(parseInt(id));
                    this._updateEmployeeTags();
                });
            });
        } else {
            // No employees selected and not "All" - show placeholder
            this.employeeTagsRef.el.innerHTML = '';
            if (this.employeeInputRef.el) {
                this.employeeInputRef.el.placeholder = 'Select Employees...';
            }
        }
    }

    _updateEmployeeDropdownData() {
        if (this.isEmployeeDropdownVisible) {
            const filteredEmps = this.allEmployees.filter(emp =>
                this.selectedDepartments.size === 0 ||
                this.selectedDepartments.has(emp.department_id[0])
            );
            this._showEmployeeDropdown(filteredEmps);
        }
    }

    async _postRenderSetup() {
        if (this.viewReportButtonRef.el) {
            this.viewReportButtonRef.el.addEventListener('click', () => this.onViewClicked());
        }
        if (this.downloadReportButtonRef.el) {
            this.downloadReportButtonRef.el.addEventListener('click', () => this.onDownloadClicked());
        }

        await this.onViewClicked();

        console.log('Custom layout, buttons, and basic filter inputs rendered.');
    }

    async _loadReportData() {
        const month = this.monthFilterInputRef.el ? this.monthFilterInputRef.el.value : '';
        const departmentIds = Array.from(this.selectedDepartments);
        const employeeIds = Array.from(this.selectedEmployees);
        const domain = [];
        if (month) {
            const [year, monthNum] = month.split('-');
            if (year && monthNum) {
                const startDate = `${year}-${monthNum}-01`;
                const endDate = new Date(year, monthNum, 0).toISOString().split('T')[0];
                domain.push(['report_date', '>=', startDate]);
                domain.push(['report_date', '<=', endDate]);
            }
        }
        if (departmentIds.length > 0) {
            domain.push(['department_id', 'in', departmentIds]);
        }
        if (employeeIds.length > 0) {
            domain.push(['employee_id', 'in', employeeIds]);
        }
        try {
            this.reportLines = await this.orm.searchRead(
                'monthly.attendance.report.line',
                domain,
                ['employee_code', 'employee_id', 'department_id', 'total_days', 'working_days', 'present_days', 'extra_days', 'pay_days', 'paid_leaves', 'unpaid_leaves','uninformed_leave','public_holidays']
            );
        } catch (error) {
            console.error('Error loading report data:', error);
            this.notification.add('Error loading report data. Please check server logs for details.', { type: 'danger' });
            this.reportLines = [];
        }
        this._renderReportData();
    }

    _renderReportData() {
        const container = this.treeViewContainerRef.el;
        const reportContainer = this.reportDataContainerRef.el;
        if (!reportContainer) {
            console.error('Report data container not found!');
            return;
        }
        reportContainer.innerHTML = '';
        if (this.reportLines.length === 0) {
            reportContainer.innerHTML = '<p>No data found for the selected filters.</p>';
            return;
        }
        let tableHtml = '<table class="o_list_view table table-sm table-hover table-striped"><thead><tr>';
        const fields = ['employee_code', 'employee_id', 'department_id', 'total_days', 'working_days', 'present_days', 'extra_days', 'pay_days', 'paid_leaves', 'unpaid_leaves','uninformed_leave','public_holidays'];
        const fieldLabels = {
            employee_code: 'EMPLOYEE CODE',
            employee_id: 'EMPLOYEE',
            department_id: 'DEPARTMENT',
            total_days: 'TOTAL DAYS',
            working_days: 'WORKING DAYS',
            present_days: 'PRESENT DAYS',
            extra_days: 'EXTRA DAYS',
            pay_days: 'PAY DAYS',
            paid_leaves: 'PAID LEAVES',
            unpaid_leaves: 'UNPAID LEAVES',
        };
        fields.forEach(field => {
            tableHtml += `<th>${fieldLabels[field] || field.replace('_', ' ').toUpperCase()}</th>`;
        });
        tableHtml += '</tr></thead><tbody>';
        this.reportLines.forEach(line => {
            tableHtml += '<tr>';
            fields.forEach(field => {
                let value = line[field];
                if (Array.isArray(value) && value.length === 2) {
                    value = value[1];
                } else if (value === false || value === null || value === undefined) {
                    value = '';
                }
                tableHtml += `<td>${value}</td>`;
            });
            tableHtml += '</tr>';
        });
        tableHtml += '</tbody></table>';
        reportContainer.innerHTML = tableHtml;
    }

    async onViewClicked() {
        const month = this.monthFilterInputRef.el ? this.monthFilterInputRef.el.value : '';
        const departmentIds = Array.from(this.selectedDepartments);
        const employeeIds = Array.from(this.selectedEmployees);
        if (!month) {
            this.notification.add('Please select a month.', { type: 'warning' });
            return;
        }
        try {
            await this.orm.call(
                'monthly.attendance.report.line',
                'generate_report_lines',
                [month, employeeIds.length > 0 ? employeeIds : null, departmentIds.length > 0 ? departmentIds : null]
            );
            await this._loadReportData();
        } catch (error) {
            console.error('Error generating report lines or loading data:', error);
            this.notification.add('Error generating report. Please check server logs for details.', { type: 'danger' });
        }
    }

    onDownloadClicked() {
        const month = this.monthFilterInputRef.el ? this.monthFilterInputRef.el.value : '';
        const departmentIds = Array.from(this.selectedDepartments);
        const employeeIds = Array.from(this.selectedEmployees);
        const departmentNames = departmentIds.map(id =>
            this.allDepartments.find(d => d.id === id)?.name
        ).filter(Boolean);
        const employeeNames = employeeIds.map(id =>
            this.allEmployees.find(e => e.id === id)?.name
        ).filter(Boolean);
        const downloadParams = {
            month: month,
            department_names: departmentNames.join(','),
            employee_names: employeeNames.join(','),
            department_ids: departmentIds.join(','),
            employee_ids: employeeIds.join(','),
        };
        const urlParams = new URLSearchParams();
        for (const key in downloadParams) {
            if (downloadParams[key]) {
                urlParams.append(key, downloadParams[key]);
            }
        }
        const downloadUrl = `/web/monthly_attendance_report/export_xlsx?${urlParams.toString()}`;
        window.location.href = downloadUrl;
    }
}

registry.category('views').add('custom_list_view', {
    type: 'list',
    display_name: 'Custom List View',
    icon: 'fa fa-list',
    multiRecord: true,
    Controller: CustomListController,
    template: 'monthly_attendance_report.CustomListView',
});