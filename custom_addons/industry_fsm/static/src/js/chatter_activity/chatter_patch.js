/** @odoo-module **/
import { patch } from "@web/core/utils/patch";
import { Chatter } from "@mail/core/web/chatter";
import { useService } from '@web/core/utils/hooks';

patch(Chatter.prototype, {

    setup() {
        super.setup?.();
        this.orm = useService("orm");
        this.rpc = useService("rpc");

        const modelName = this.env.model?.root?.resModel;
        const recordId = this.env.model?.root?.resId;
        console.log(recordId);

        this.showDownloadButton = false;

        if (modelName === "project.task" && recordId) {
            this.rpc('/get/fetch_ticket_number', { task_id: recordId }).then((result) => {
                const isFsm = result?.is_fsm;
                console.log("is_fsm from controller:", isFsm);
                this.showDownloadButton = isFsm === true;
            });
        }
    },
    async downloadChat() {
        const messageDivs = document.querySelectorAll('.o-mail-Message-core');
        const messages = [];

        for (const div of messageDivs) {
            const messageBodyElement = div.querySelector('.o-mail-Message-content');
            if (!messageBodyElement) continue;

            let text = "";
            const clone = messageBodyElement.cloneNode(true);
            clone.querySelectorAll('.o-mail-AttachmentCard').forEach(el => el.remove());
            const meaningfulText = clone.textContent.trim();

            if (!meaningfulText) {
                text = "";
            } else {
                const messageTexts = [];
                const trackingOldElements = messageBodyElement.querySelectorAll('span.o-mail-Message-trackingOld');
                const trackingNewElements = messageBodyElement.querySelectorAll('span.o-mail-Message-trackingNew');
                const trackingFieldElements = messageBodyElement.querySelectorAll('span.o-mail-Message-trackingField');

                for (let i = 0; i < Math.min(trackingOldElements.length, trackingNewElements.length); i++) {
                    const oldText = trackingOldElements[i].textContent.trim();
                    const newText = trackingNewElements[i].textContent.trim();
                    const fieldText = trackingFieldElements[i].textContent.trim();
                    messageTexts.push(`from ${oldText} to ${newText} ${fieldText}`);
                }

                if (messageTexts.length === 0 && meaningfulText) {
                    messageTexts.push(meaningfulText);
                }

                text = messageTexts.join('\n');
            }

            const authorElement = div.querySelector('.o-mail-Message-author');
            const actionBy = authorElement ? authorElement.textContent.trim() : "Unknown";

            const dateTimeElement = div.querySelector('small.o-mail-Message-date');
            let dateTime = "Unknown";
            if (dateTimeElement) {
                const raw = dateTimeElement.getAttribute("title");
                const parsedDate = raw ? new Date(raw) : null;
                if (!isNaN(parsedDate)) {
                    const day = String(parsedDate.getDate()).padStart(2, '0');
                    const month = String(parsedDate.getMonth() + 1).padStart(2, '0');
                    const year = parsedDate.getFullYear();

                    let hours = parsedDate.getHours();
                    const minutes = String(parsedDate.getMinutes()).padStart(2, '0');
                    const seconds = String(parsedDate.getSeconds()).padStart(2, '0');
                    const ampm = hours >= 12 ? 'PM' : 'AM';
                    hours = hours % 12 || 12;
                    hours = String(hours).padStart(2, '0');

                    dateTime = `${day}/${month}/${year}, ${hours}:${minutes}:${seconds} ${ampm}`;
                }
            }

            const attachments = [];

            // Handle image attachments
            const imageCards = div.querySelectorAll('.o-mail-AttachmentImage img');
            for (const imgTag of imageCards) {
                const parentCard = imgTag.closest('.o-mail-AttachmentCard');
                const fileName = parentCard?.getAttribute('title') || parentCard?.getAttribute('aria-label') || 'Image Attachment';

                try {
                    const originalSrc = imgTag.getAttribute('src');
                    const urlObj = new URL(originalSrc, window.location.origin);
                    urlObj.searchParams.delete('width');
                    urlObj.searchParams.delete('height');
                    const cleanSrc = urlObj.toString();

                    imgTag.setAttribute('src', cleanSrc);
                    imgTag.removeAttribute('height');
                    imgTag.removeAttribute('width');
                    imgTag.style.height = null;
                    imgTag.style.width = null;

                    const base64 = await this.imageToBase64(imgTag);

                    attachments.push({
                        type: 'image',
                        base64: base64.base64,
                        url: cleanSrc,
                        name: fileName,
                    });
                } catch (err) {
                    console.warn("Image conversion failed:", err);
                }
            }

            // Handle file names (for matching later)
            const fileCards = div.querySelectorAll('.o-mail-AttachmentCard');
            const fileNamesInChatter = [];

            for (const card of fileCards) {
                const downloadBtn = card.querySelector('button[data-download-url]');
                const fileName = card.getAttribute('title') || card.getAttribute('aria-label') || downloadBtn?.getAttribute('title');
                if (fileName) {
                    fileNamesInChatter.push(fileName.trim());
                }
            }

            // Skip message if no content at all
            if (!text && attachments.length === 0 && fileNamesInChatter.length === 0) {
                continue;
            }

            messages.push({
                text,
                actionBy,
                dateTime,
                attachments: attachments.filter(Boolean),
                chatterFileNames: fileNamesInChatter,
            });
        }

        // Fetch ir.attachment data
        const taskId = this.env.model?.root?.resId;
        const ticketInfo = await this.fetchTicketInfo(taskId);
        const baseUrl = window.location.origin;

        // Match IR attachment files with chatter
        if (ticketInfo.attachments?.length) {
            ticketInfo.attachments.forEach((file) => {
                const fileDateTime = file.create_date;
                const fileDateTimeTrimmed = fileDateTime.slice(0, 17);

                const fileUrl = `${baseUrl}/web/content/${file.id}`;
                const fileName = file.name?.trim();

                const matchedMsg = messages.find((msg) => {
                    const msgTimeTrimmed = msg.dateTime.slice(0, 17);
                    const fileTimeTrimmed = file.create_date.slice(0, 17);
                    return (
                        msgTimeTrimmed === fileTimeTrimmed &&
                        msg.chatterFileNames.includes(file.name?.trim())
                    );
                });

                if (matchedMsg) {
                    matchedMsg.attachments = matchedMsg.attachments || [];
                    matchedMsg.attachments.push({
                        type: 'file',
                        name: fileName,
                        url: fileUrl
                    });
                } else {
                    console.warn(`No match for: ${fileName} at ${fileDateTime}`);
                }
            });
        }

        this.downloadAsPDF(messages, ticketInfo);
    },

    async fetchTicketInfo(taskId) {
        try {
            const response = await this.rpc('/get/fetch_ticket_number', { task_id: taskId });
            return {
                ticket_number: response.ticket_number || "Unknown",
                assignee: response.assignee?.join(', ') || "Unassigned",
                call_type: response.call_type || "N/A",
                complaint_type: response.complaint_type || "N/A",
                reason_code_id: response.reason_code_id || "N/A",
                call_name: response.call_name || "N/A",
                customer: response.customer || "N/A",
                customer_product_id: response.customer_product_id || "N/A",
                serial_number: response.serial_number || "N/A",
                service_types: response.service_types || "N/A",
                call_coordinator_id: response.call_coordinator_id || "N/A",
                call_coordinator_phone: response.call_coordinator_phone || "N/A",
                stage_name: response.stage_name || "N/A",
                start_date: response.start_date || "N/A",
                end_date: response.end_date || "N/A",
                problem_description: response.problem_description || "N/A",
                fix_description: response.fix_description || "N/A",
                call_sub_types: response.call_sub_types || "N/A",
                priority: response.priority || "N/A",
                call_sub_type_assignee: response.call_sub_type_assignee || "N/A",
                attachments: response.attachments || [],
            };
        } catch (error) {
            console.error("Error fetching ticket info:", error);
            return {
                ticket_number: "Unknown",
                assignee: "Unknown",
                call_type: "Unknown",
                complaint_type: "Unknown",
                reason_code_id: "Unknown",
                call_name: "Unknown",
                customer: "Unknown",
                customer_product_id: "Unknown",
                serial_number: "Unknown",
                service_types: "Unknown",
                call_coordinator_id: "Unknown",
                call_coordinator_phone: "Unknown",
                stage_name: "Unknown",
                start_date: "Unknown",
                end_date: "Unknown",
                problem_description: "Unknown",
                fix_description: "Unknown",
                call_sub_types: "Unknown",
                priority: "Unknown",
                call_sub_type_assignee: "Unknown",
                attachments: [],
            };
        }
    },

    imageToBase64: function (imgElement) {
        return new Promise((resolve, reject) => {
            const img = new Image();
            img.crossOrigin = "Anonymous";
            img.onload = () => {
                const canvas = document.createElement('canvas');
                canvas.width = img.width;
                canvas.height = img.height;
                const ctx = canvas.getContext('2d');
                ctx.drawImage(img, 0, 0);
                resolve({
                    base64: canvas.toDataURL('image/png'),
                    src: imgElement.src
                });
            };
            img.onerror = reject;
            img.src = imgElement.src;
        });
    },

    fetchCompanyLogo: async function () {
        try {
            const taskId = this.env.model?.root?.resId;

            const taskResponse = await this.rpc('/web/dataset/call_kw', {
                model: 'project.task',
                method: 'read',
                args: [[taskId]],
                kwargs: { fields: ['id', 'company_id'] }
            });

            if (taskResponse && taskResponse.length > 0 && taskResponse[0].company_id) {
                const task = taskResponse[0];
                const companyId = task.company_id[0];

                const companyResponse = await this.rpc('/web/dataset/call_kw', {
                    model: 'res.company',
                    method: 'read',
                    args: [[companyId]],
                    kwargs: { fields: ['name', 'logo'] }
                });

                if (companyResponse && companyResponse.length > 0) {
                    const company = companyResponse[0];

                    if (company.logo) {
                        return `data:image/png;base64,${company.logo}`;
                    }
                }
            }
        } catch (error) {
            console.error("Failed to fetch company logo:", error);
        }
        return null;
    },

    async downloadAsPDF(messages, ticketInfo, modelName) {
        const { jsPDF } = window.jspdf;
        const doc = new jsPDF();

        const companyLogo = await this.fetchCompanyLogo();

        if (companyLogo) {
            const logoWidth = 20;
            const logoHeight = 20;
            doc.addImage(companyLogo, 'auto', 10, 10, logoWidth, logoHeight);
        }

        const marginX = 15;
        let y = 20;
        const labelFontSize = 10;
        const valueFontSize = 9;
        const lineHeight = 3;
        const cellPadding = 4;
        const borderColor = [180, 180, 180];
        const labelBgColor = [230, 230, 230];

        const col1Width = 45;
        const col2Width = 45;
        const col3Width = 45;
        const col4Width = 45;

        function drawCenteredText(text, x, y, width, height, fontSize) {
            doc.setFontSize(fontSize);
            const textWidth = doc.getTextWidth(text);
            const textX = x + width / 2;
            const textY = y + height / 2 + fontSize / 6; // vertical center adjustment

            doc.text(text, textX, textY, { align: 'center' });
        }

        const drawRow = (label, value, col1Width, col2Width) => {
            const lineGap = 2;

            // Split text and calculate height
            const textLines = doc.splitTextToSize(value || "", col2Width - 2 * cellPadding);
            const textHeight = textLines.length * (lineHeight + lineGap) - lineGap;
            const rowHeight = textHeight + 2 * cellPadding;

            // Draw label cell
            doc.setFillColor(...labelBgColor);
            doc.setDrawColor(...borderColor);
            doc.rect(marginX, y, col1Width, rowHeight, 'FD');

            // Draw value cell background (if needed, you can set fill here)
            doc.setFillColor(255, 255, 255); // white background for value
            doc.rect(marginX + col1Width, y, col2Width, rowHeight, 'F'); // fill
            doc.setDrawColor(...borderColor);
            doc.rect(marginX + col1Width, y, col2Width, rowHeight, 'S'); // border

            // Draw label text
            doc.setFont("helvetica", "bold");
            const labelPadding = 4;
            drawCenteredText(label, marginX, y + labelPadding, col1Width, rowHeight - 2 * labelPadding, labelFontSize);

            // Draw value text
            doc.setFont("helvetica", "normal");
            doc.setFontSize(valueFontSize);

            const valueTextHeight = textHeight + 2 * cellPadding;
            let textY = y + (rowHeight - valueTextHeight) / 2 + valueFontSize / 1.4;
            textLines.forEach(line => {
                const textX = marginX + col1Width + cellPadding;
                doc.text(line, textX, textY);
                textY += lineHeight + lineGap;
            });

            // Update y for next row
            y += rowHeight;
        };

        const sectionTitle = (title) => {
            doc.setFont("helvetica", "bold");
            doc.setFontSize(12);
            doc.text(title, marginX + 90, y, { align: 'center' });
            doc.setFontSize(valueFontSize);
            y += 6;
        };

        const drawComplaintRow = (label1, value1, label2, value2) => {
            const textLines1 = doc.splitTextToSize(value1 || "", col2Width - 2 * cellPadding);
            const textLines2 = doc.splitTextToSize(value2 || "", col4Width - 2 * cellPadding);
            const rowHeight = Math.max(textLines1.length * lineHeight, textLines2.length * lineHeight) + cellPadding * 2;

            doc.setDrawColor(...borderColor);
            doc.setFillColor(...labelBgColor);
            doc.rect(marginX, y, col1Width, rowHeight, 'FD');
            doc.rect(marginX + col1Width + col2Width, y, col3Width, rowHeight, 'FD');
            doc.rect(marginX + col1Width, y, col2Width, rowHeight);
            doc.rect(marginX + col1Width + col2Width + col3Width, y, col4Width, rowHeight);

            doc.setFont("helvetica", "bold");
            drawCenteredText(label1, marginX, y, col1Width, rowHeight, labelFontSize);
            drawCenteredText(label2, marginX + col1Width + col2Width, y, col3Width, rowHeight, labelFontSize);

            doc.setFont("helvetica", "normal");
            doc.setFontSize(valueFontSize);

            let textY1 = y + (rowHeight - textLines1.length * lineHeight) / 2 + lineHeight - 1;
            textLines1.forEach(line => {
                doc.text(line, marginX + col1Width + cellPadding, textY1);
                const lineGap = 2;
                textY1 += lineHeight + lineGap;
            });

            let textY2 = y + (rowHeight - textLines2.length * lineHeight) / 2 + lineHeight - 1;
            textLines2.forEach(line => {
                doc.text(line, marginX + col1Width + col2Width + col3Width + cellPadding, textY2);
                const lineGap = 2;
                textY2 += lineHeight + lineGap;
            });

            y += rowHeight;
        };

        y += 20;

        sectionTitle(`Call Details For Ticket ID: ${ticketInfo.ticket_number}`);
        drawComplaintRow("Customer", ticketInfo.customer, "Product", ticketInfo.customer_product_id);
        drawComplaintRow("Serial Number", ticketInfo.serial_number, "Call Type", ticketInfo.call_type);
        drawComplaintRow("Service Type", ticketInfo.service_types,  "Priority", ticketInfo.priority);
        drawComplaintRow("Start Date/Time", ticketInfo.start_date, "End Date/Time", ticketInfo.end_date);
        drawComplaintRow("Stage", ticketInfo.stage_name,  "Assignee", ticketInfo.assignee);
        drawComplaintRow("Call Coordinator", ticketInfo.call_coordinator_id,  "Call Coordinator No.", ticketInfo.call_coordinator_phone);
        drawComplaintRow("Complaint Type", ticketInfo.complaint_type,  "Reason Code", ticketInfo.reason_code_id);
        drawComplaintRow("Call Sub Type", ticketInfo.call_sub_types, "Call Sub Type Assignee", ticketInfo.call_sub_type_assignee);

        y += 25;

        // Section 2 - Reported Problem
        sectionTitle("Reported Problem");
        drawRow("Problem Description", ticketInfo.call_name, 50, 130);
        drawRow("Actual Problem", ticketInfo.problem_description, 50, 130);
        drawRow("Problem Solution", ticketInfo.fix_description, 50, 130);

        // Section 3 - Chatter Messages
        doc.addPage();
        y = 20;

        sectionTitle("Chatter Messages");

        const colWidths = [50, 80, 50];
        const colHeaders = ["Date-Time", "Message", "Action By"];

        const drawChatterHeader = () => {
            doc.setDrawColor(...borderColor);
            let x = marginX;
            const cellHeight = lineHeight + 6;

            doc.setFont("helvetica", "bold");
            doc.setFontSize(labelFontSize);

            colHeaders.forEach((header, idx) => {
                const colWidth = colWidths[idx];
                doc.setFillColor(...labelBgColor);
                doc.rect(x, y, colWidth, cellHeight, 'FD');
                const textY = y + (cellHeight / 2) + 1.5;
                doc.text(header, x + colWidth / 2, textY, { align: 'center' });
                x += colWidth;
            });

            doc.setFont("helvetica", "normal");
            doc.setFontSize(valueFontSize);

            y += cellHeight;
        };

	drawChatterHeader();

	for (const msg of messages) {
	    const maxTextLength = colWidths[1] - 2 * cellPadding;
	    const messageLines = doc.splitTextToSize(msg.text || "", maxTextLength);

	    const imgWidth = 30;
	    const imgHeight = 20;
	    const imageSpacing = 3;
	    const fileLineHeight = 12;

	    const dynamicLineHeight = Math.max(lineHeight, messageLines.length > 1 ? lineHeight + 2 : lineHeight);
	    const messageHeight = messageLines.length * dynamicLineHeight;

	    // Filter valid attachments
	    const validAttachments = (msg.attachments || []).filter(att => {
		return att && (att.type === 'image' || att.type === 'file') && (att.base64 || att.url);
	    });

	    // Calculate image and file attachment heights separately
	    let imageAttachmentsHeight = 0;
	    let fileAttachmentsHeight = 0;

	    for (const attachment of validAttachments) {
		if (attachment.type === 'image') {
		    imageAttachmentsHeight += imgHeight + imageSpacing;
		} else if (attachment.type === 'file') {
		    const textWidthLimit = colWidths[1] - 2 * cellPadding;
		    const lines = doc.splitTextToSize(attachment.name || '', textWidthLimit);
		    fileAttachmentsHeight += lines.length * fileLineHeight;
		}
	    }

	    const attachmentsHeight = imageAttachmentsHeight + fileAttachmentsHeight;

	    // Final row height
	    const rowHeight = Math.max(
		messageHeight + attachmentsHeight + cellPadding,
		dynamicLineHeight + cellPadding * 2
	    );

	    // Page break check
	    if (y + rowHeight > 280) {
		doc.addPage();
		y = 20;
		drawChatterHeader();
	    }

	    let x = marginX;

	    // Date-Time Cell
	    doc.rect(x, y, colWidths[0], rowHeight);
	    drawCenteredText(msg.dateTime, x, y, colWidths[0], rowHeight, valueFontSize);
	    x += colWidths[0];

	    // Message + Attachments Cell
	    doc.rect(x, y, colWidths[1], rowHeight);

	    const totalContentHeight = messageHeight + attachmentsHeight;
	    let contentStartY = y + (rowHeight - totalContentHeight) / 2;

	    let msgY = contentStartY;

	    // Render message text
	    messageLines.forEach((line) => {
		doc.text(line, x + cellPadding, msgY + dynamicLineHeight);
		msgY += dynamicLineHeight;
	    });

	    for (const attachment of validAttachments) {
		try {
		    if (attachment.type === 'image') {
		        const imgX = x + (colWidths[1] - imgWidth) / 2;
		        doc.addImage(attachment.base64, "JPEG", imgX, msgY, imgWidth, imgHeight);
		        if (attachment.url) {
		            doc.link(imgX, msgY, imgWidth, imgHeight, { url: attachment.url });
		        }
		        msgY += imgHeight + imageSpacing;
		    } else if (attachment.type === 'file') {
		        const textX = x + cellPadding;
		        const textWidthLimit = colWidths[1] - 2 * cellPadding;
		        const lines = doc.splitTextToSize(attachment.name || '', textWidthLimit);

		        doc.setFontSize(9);
		        for (const line of lines) {
		            doc.textWithLink(line, textX, msgY + 6, {
		                url: attachment.url,
		            });
		            msgY += fileLineHeight;
		        }
		    }
		} catch (err) {
		    console.warn("Attachment render failed:", err);
		}
	    }

            x += colWidths[1];

            // Action By cell
            doc.rect(x, y, colWidths[2], rowHeight);
            drawCenteredText(msg.actionBy, x, y, colWidths[2], rowHeight, valueFontSize);

            y += rowHeight;
        }
        doc.save(`${ticketInfo.ticket_number}_${ticketInfo.customer}.pdf`);
    }
});
