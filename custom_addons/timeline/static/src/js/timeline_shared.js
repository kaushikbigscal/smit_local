/** @odoo-module **/
import { registry } from "@web/core/registry";
let selectedModelIds = [];

/**
 * Get the current timeline model from the page context
 */
function getCurrentTimelineModel() {
    const container = document.getElementById("timeline_container");
    if (container?.dataset.resModel) {
        return container.dataset.resModel;
    }
    console.warn("Falling back to default: customer.timeline");
    return "customer.timeline";
}

/**
 * Filter Timeline by model
 */
async function filterTimelineByModel(modelId, btnEl) {
    try {
        const model = getCurrentTimelineModel();
        const container = document.getElementById('timeline_container');
        if (!container || !container.dataset.resId) return;
        // Remove selected_btn class from ALL buttons first
        document.querySelectorAll('.model_filter_btn').forEach(btn => {
            btn.classList.remove('selected_btn');
        });
        // Then add selected_btn class only to the clicked button
        btnEl.classList.add('selected_btn');
        const result = await fetch("/web/dataset/call_kw", {
            method: "POST",
            credentials: "same-origin",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                jsonrpc: "2.0",
                method: "call",
                params: {
                    model: model,
                    method: "filter_timeline_data",
                    args: [modelId],
                    kwargs: {
                        context: { active_id: parseInt(container.dataset.resId) }
                    },
                },
            }),
        });
        const response = await result.json();
        if (response.result && response.result.html) {
            container.innerHTML = response.result.html;
        }
    } catch (error) {
        console.error('Timeline filtering failed:', error);
        const container = document.getElementById('timeline_container');
        if (container) {
            container.innerHTML = `
                <div class="alert alert-danger">
                    Unable to filter timeline. Please refresh the page and try again.
                </div>
            `;
        }
    }
}
function initializeTimelineEvents() {
    document.querySelectorAll('.timeline_date_header').forEach(header => {
        header.addEventListener('click', () => toggleDateSection(header));
    });
    document.querySelectorAll('.model_header').forEach(header => {
        header.addEventListener('click', () => toggleModelGroup(header));
    });
}
 /**
 * Clear selection (All button)
 */
async function clearSelection(allBtnEl) {
    document.querySelectorAll('.model_filter_btn').forEach(btn => {
        btn.classList.remove("selected_btn");
    });
    allBtnEl.classList.add("selected_btn");
    document.querySelectorAll('.model_filter_btn').forEach(btn => {
        btn.style.transform = 'translateY(0)';
    });
    const container = document.getElementById('timeline_container');
    if (!container || !container.dataset.resId) return;
    try {
        const result = await fetch("/web/dataset/call_kw", {
            method: "POST",
            credentials: "same-origin",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                jsonrpc: "2.0",
                method: "call",
                params: {
                    model: getCurrentTimelineModel(),
                    method: "filter_timeline_data",
                    args: ['all'],
                    kwargs: {
                        context: { active_id: parseInt(container.dataset.resId) }
                    },
                },
            }),
        });
        const response = await result.json();
        if (response.result && response.result.html) {
            container.innerHTML = response.result.html;
        }
    } catch (err) {
        console.error("Timeline filtering failed:", err);
    }
}
/**
 * Apply model filters via RPC
 */
async function applyModelFilters(resId) {
    try {
        const values = selectedModelIds.length
            ? { selected_model_ids: [[6, 0, selectedModelIds.map(Number)]], active_model: null }
            : { selected_model_ids: [[5]], active_model: "all" };
        const currentModel = getCurrentTimelineModel();
        const resp = await fetch("/web/dataset/call_kw", {
            method: "POST",
            credentials: "same-origin",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                jsonrpc: "2.0",
                method: "call",
                params: {
                    model: currentModel,
                    method: "write",
                    args: [[resId], values],
                    kwargs: { context: {} },
                },
            }),
        });
        const result = await resp.json();
        if (!result.error) window.location.reload();
    } catch (err) {
        console.error("applyModelFilters error:", err);
    }
}
/**
 * Open timeline record using Odoo action service
 */
function openTimelineRecord(model, id) {
    const actionService = registry.category("services").get("action");
    if (!model || !id || !actionService) return;
    actionService.doAction({
        type: "ir.actions.act_window",
        res_model: model,
        res_id: id,
        views: [[false, "form"]],
        target: "current",
    });
}
/**
 * Toggle date sections
 */
 function toggleDateSection(element) {
    const container = element.nextElementSibling;
    const icon = element.querySelector('.toggle_icon');
    if (container.classList.contains('expanded')) {
        container.classList.remove('expanded');
        element.classList.add('collapsed');
        icon.innerHTML = '▼';
    } else {
        container.classList.add('expanded');
        element.classList.remove('collapsed');
        icon.innerHTML = '▲';
        container.querySelectorAll('.model_records').forEach(group => {
            group.classList.add('collapsed');
        });
        container.querySelectorAll('.model_header .toggle_icon').forEach(icon => {
            icon.innerHTML = '▼';
        });
    }
}
/**
 * Toggle model groups
 */
function toggleModelGroup(element) {
    const container = element.nextElementSibling;
    const icon = element.querySelector('.toggle_icon');
    if (container.classList.contains('expanded')) {
        container.classList.remove('expanded');
        element.classList.remove('collapsed');
        icon.innerHTML = '▼';
    } else {
        container.classList.add('expanded');
        element.classList.add('collapsed');
        icon.innerHTML = '▲';
    }
}
/**
 * Toggle mobile "More" dropdown
 */
function toggleMobileMoreDropdown() {
    const content = document.getElementById('mobileDropdownContent');
    const toggle = document.querySelector('.mobile_more_btn');
    if (content && toggle) {
        content.classList.toggle('show');
        toggle.classList.toggle('active');
    }
}
/**
 * Initialize mobile filter events
 */
function initializeMobileFilters() {
    document.addEventListener('click', function(event) {
        const dropdown = document.querySelector('.mobile_more_dropdown');
        const content = document.getElementById('mobileDropdownContent');
        const toggle = document.querySelector('.mobile_more_btn');
        if (dropdown && !dropdown.contains(event.target) && content && content.classList.contains('show')) {
            content.classList.remove('show');
            if (toggle) toggle.classList.remove('active');
        }
    });
    window.addEventListener('resize', function() {
        const content = document.getElementById('mobileDropdownContent');
        const toggle = document.querySelector('.mobile_more_btn');
        if (window.innerWidth > 768 && content && content.classList.contains('show')) {
            content.classList.remove('show');
            if (toggle) toggle.classList.remove('active');
        }
    });
}
document.addEventListener("DOMContentLoaded", () => {
    const container = document.getElementById('timeline_container');
    if (container && container.dataset.loaded === "1") {
        const allBtn = document.querySelector('.model_filter_btn');
        if (allBtn) {
            document.querySelectorAll('.model_filter_btn').forEach(btn => {
                btn.classList.remove('selected_btn');
            });
            allBtn.classList.add('selected_btn');
        }
    }
    initializeTimelineEvents();
    initializeMobileFilters();
});

window.filterTimelineByModel = filterTimelineByModel;
window.clearSelection = clearSelection;
window.toggleDateSection = toggleDateSection;
window.toggleModelGroup = toggleModelGroup;
window.toggleMobileMoreDropdown = toggleMobileMoreDropdown;