/** @odoo-module **/

//qr_scanner_dialog.js

import { Component, onMounted, onWillUnmount, useRef } from "@odoo/owl";
import { Dialog } from "@web/core/dialog/dialog";

export class QrScannerDialog extends Component {
    static components = { Dialog };
    static template = "barcode_container.QrScannerDialog";

    setup() {
        this.videoRef = useRef("video");
        this.canvasRef = useRef("canvas");
        this.scanning = true;

        onMounted(() => this.startScanner());
        onWillUnmount(() => this.stopCamera());
    }

    async startScanner() {
        this.video = this.videoRef.el;
        this.canvas = this.canvasRef.el;

        if (!this.video || !this.canvas) {
            console.error("❌ Video or Canvas element not found in DOM!");
            return;
        }

        try {
            const stream = await navigator.mediaDevices.getUserMedia({
                video: { facingMode: "environment" }
            });

            console.log("✅ Camera stream obtained:", stream);

            this.video.srcObject = stream;
            this.video.onloadedmetadata = () => {
                console.log("▶️ Playing video...");
                this.video.play();
                this.scanLoop();
            };
        } catch (err) {
            console.error("❌ Camera error:", err);
        }
    }

    scanLoop() {
        const ctx = this.canvas.getContext("2d", { willReadFrequently: true });

        const tick = () => {
            if (!this.scanning) return;

            if (this.video.readyState === this.video.HAVE_ENOUGH_DATA) {
                this.canvas.width = this.video.videoWidth;
                this.canvas.height = this.video.videoHeight;
                ctx.drawImage(this.video, 0, 0, this.canvas.width, this.canvas.height);

                const imageData = ctx.getImageData(0, 0, this.canvas.width, this.canvas.height);
                const code = window.jsQR && window.jsQR(imageData.data, imageData.width, imageData.height, {
                    inversionAttempts: "dontInvert"
                });

                if (code) {
                    console.log("✅ QR Detected:", code.data);
                    this.scanning = false;
                    this.onQrDetected(code.data);
                    return;
                }
            }
            requestAnimationFrame(tick);
        };

        tick();
    }

    async onQrDetected(data) {
        try {
            const payload = JSON.parse(data);
            console.log("📤 Sending payload:", payload);

            const result = await this.env.services.rpc("/barcode/container/scan", payload);

            if (result.success && result.matched) {
                // ✅ Use notification instead of alert (non-blocking)
                this.env.services.notification.add(
                    `✅ Line marked scanned: ${payload.label}`,
                    { type: "success" }
                );

                // ✅ Close dialog first to avoid DOM conflict
                this.closeDialog();

                // ✅ Then safely redirect
                this.env.services.action.doAction({
                    type: "ir.actions.act_window",
                    res_model: "barcode.container",
                    views: [[false, "list"], [false, "form"]],
                    domain: [["id", "=", payload.container_id]],
                });
            } else {
                this.env.services.notification.add(
                    `⚠️ No matching line found for: ${payload.label}`,
                    { type: "warning" }
                );
                this.closeDialog();
            }
        } catch (err) {
            console.error("❌ Server error:", err);
            this.env.services.notification.add("Server error while scanning container.", {
                type: "danger",
            });
            this.closeDialog();
        } finally {
            this.closeDialog();
        }
    }

    stopCamera() {
        if (this.video?.srcObject) {
            this.video.srcObject.getTracks().forEach(track => track.stop());
        }
    }

    closeDialog() {
        this.scanning = false;
        this.stopCamera();
        if (this.props.close) this.props.close();
    }
}
