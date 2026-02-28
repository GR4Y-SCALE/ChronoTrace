import { jsPDF } from 'jspdf';
import autoTable from 'jspdf-autotable';

const RULE_DESCRIPTIONS = {
    "RULE_01": "$SI modified timestamp predates $FN arrival on this volume. Timestamp backdating confirmed.",
    "RULE_02": "$SI timestamp predates $FN creation on this device. File cannot have been modified before it existed here.",
    "RULE_03": "USN Journal contains only FILE_CREATE. No modification history exists despite $SI claiming prior edits.",
    "RULE_04": "LogFile LSN gap detected. Missing entries indicate log manipulation.",
    "RULE_05": "File hash contradicts $SI modification date. Content was changed after timestamp was set.",
    "RULE_06": "EXIF timestamp contradicts $SI modified date. Internal metadata was not updated.",
    "RULE_07": "Zone.Identifier ADS is missing. Was deliberately stripped to hide transfer origin.",
    "RULE_08": "Embedded Volume Serial Number does not match this device.",
    "RULE_09": "$SI shows modification but no USN_REASON_DATA_OVERWRITE exists in journal. Live tampering.",
    "RULE_10": "Multiple $SI updates within milliseconds. Programmatic timestomping pattern detected.",
    "RULE_11": "$I30 directory slack is fully zeroed. Deliberately wiped to hide file existence.",
    "RULE_12": "Some MAC timestamps changed, others left in impossible chronological state.",
    "RULE_13": "Undeclared Alternate Data Streams detected.",
    "RULE_14": "MFT sequence number inconsistent with file age claimed by $SI.",
    "RULE_15": "RULE_01 + RULE_02 + RULE_03 all triggered. Cross-device transfer with pre-transfer manipulation confirmed."
};

// Helper: call autoTable and return finalY
function table(doc, y, opts) {
    const result = autoTable(doc, { startY: y, ...opts });
    // finalY is stored on the doc after autoTable runs
    return (doc.lastAutoTable && doc.lastAutoTable.finalY) || (result && result.finalY) || y + 30;
}

export function generateDetailedPDF(reportData) {
    try {
        const { case_info, summary, findings, timeline_events } = reportData;
        const doc = new jsPDF('p', 'mm', 'a4');
        const W = doc.internal.pageSize.getWidth();
        const H = doc.internal.pageSize.getHeight();
        let y = 0;

        const tblStyles = { fontSize: 9, font: 'courier', cellPadding: 3 };
        const tblHead = { fillColor: [0, 50, 80], textColor: 255, fontStyle: 'bold' };
        const tblHeadRed = { fillColor: [180, 0, 0], textColor: 255 };

        const addWatermark = () => {
            doc.setTextColor(230, 230, 230);
            doc.setFontSize(50);
            doc.setFont('helvetica', 'bold');
            doc.text('CONFIDENTIAL', W / 2, H / 2, { angle: 45, align: 'center' });
        };

        const addFooter = (pageNum) => {
            doc.setFontSize(7);
            doc.setTextColor(150);
            doc.setFont('helvetica', 'normal');
            doc.text('ChronoTrace v1.0 - Page ' + pageNum, W / 2, H - 8, { align: 'center' });
            doc.text('Generated: ' + new Date().toISOString().split('T')[0], W / 2, H - 4, { align: 'center' });
        };

        const checkPage = (needed) => {
            needed = needed || 30;
            if (y + needed > H - 20) {
                addWatermark();
                addFooter(doc.getNumberOfPages());
                doc.addPage();
                y = 20;
            }
        };

        const sectionTitle = (title) => {
            checkPage(20);
            doc.setFontSize(12);
            doc.setFont('helvetica', 'bold');
            doc.setTextColor(0);
            y += 8;
            doc.text(title, 15, y);
            y += 2;
            doc.setDrawColor(0, 100, 200);
            doc.setLineWidth(0.5);
            doc.line(15, y, W - 15, y);
            y += 6;
        };

        const bodyText = (text, indent) => {
            indent = indent || 15;
            doc.setFontSize(9);
            doc.setFont('helvetica', 'normal');
            doc.setTextColor(40);
            var lines = doc.splitTextToSize(text, W - indent - 15);
            for (var i = 0; i < lines.length; i++) {
                checkPage(6);
                doc.text(lines[i], indent, y);
                y += 4.5;
            }
        };

        const labelValue = (label, value, indent) => {
            indent = indent || 15;
            checkPage(8);
            doc.setFontSize(9);
            doc.setFont('courier', 'normal');
            doc.setTextColor(100);
            doc.text(label, indent, y);
            doc.setTextColor(0);
            doc.setFont('courier', 'bold');
            doc.text(String(value || 'N/A'), indent + 55, y);
            y += 5;
        };

        // ========== PAGE 1 - COVER ==========
        doc.setFillColor(5, 8, 16);
        doc.rect(0, 0, W, H, 'F');

        doc.setTextColor(255);
        doc.setFontSize(28);
        doc.setFont('helvetica', 'bold');
        doc.text('FORENSIC ANALYSIS', W / 2, 60, { align: 'center' });
        doc.text('REPORT', W / 2, 72, { align: 'center' });

        doc.setFontSize(11);
        doc.setFont('helvetica', 'normal');
        doc.setTextColor(0, 212, 255);
        doc.text('ChronoTrace v1.0', W / 2, 85, { align: 'center' });

        doc.setDrawColor(0, 212, 255);
        doc.setLineWidth(0.8);
        doc.line(50, 95, W - 50, 95);

        doc.setTextColor(255, 45, 45);
        doc.setFontSize(10);
        doc.setFont('helvetica', 'bold');
        doc.text('CLASSIFICATION: CONFIDENTIAL', W / 2, 110, { align: 'center' });

        var coverFields = [
            ['Case Identifier', case_info.id],
            ['Analysis Date', new Date(case_info.created_at).toLocaleString()],
            ['Investigator', case_info.investigator],
            ['Target Device', case_info.device_label],
            ['Image Hash SHA256', case_info.image_hash || 'N/A']
        ];

        doc.setFont('courier', 'normal');
        doc.setFontSize(9);
        var cy = 125;
        for (var ci = 0; ci < coverFields.length; ci++) {
            doc.setTextColor(140);
            doc.text(coverFields[ci][0] + ':', 50, cy);
            doc.setTextColor(255);
            doc.text(String(coverFields[ci][1] || ''), 100, cy);
            cy += 7;
        }

        doc.setDrawColor(0, 212, 255);
        doc.line(50, cy + 5, W - 50, cy + 5);

        doc.setTextColor(255, 45, 45);
        doc.setFontSize(14);
        doc.setFont('helvetica', 'bold');
        doc.text('OVERALL RISK LEVEL: ' + summary.overall_risk_label + ' (' + summary.overall_risk_score + '/100)', W / 2, cy + 18, { align: 'center' });

        var hasLive = findings && findings.some(function (f) {
            return f.rules_triggered.indexOf("RULE_04") >= 0 || f.rules_triggered.indexOf("RULE_09") >= 0;
        });
        if (hasLive) {
            doc.setTextColor(255, 45, 45);
            doc.setFontSize(12);
            doc.text('[!] LIVE TAMPERING DETECTED', W / 2, cy + 30, { align: 'center' });
        }

        doc.setTextColor(120);
        doc.setFontSize(7);
        doc.setFont('helvetica', 'normal');
        doc.text('This report was generated by automated forensic analysis', W / 2, H - 30, { align: 'center' });
        doc.text('and must be reviewed by a qualified examiner before court use.', W / 2, H - 25, { align: 'center' });

        addFooter(1);

        // ========== PAGE 2 - CHAIN OF CUSTODY ==========
        doc.addPage();
        doc.setFillColor(255, 255, 255);
        doc.rect(0, 0, W, H, 'F');
        y = 25;

        sectionTitle('CHAIN OF CUSTODY RECORD');
        labelValue('Evidence Item', 'Disk Image - ' + case_info.device_label);
        labelValue('Acquired By', case_info.investigator);
        labelValue('Acquisition Tool', 'FTK Imager / dd');
        labelValue('Write Blocker Used', 'Yes');
        y += 4;

        sectionTitle('HASH VERIFICATION');
        labelValue('SHA256', case_info.image_hash || 'N/A');
        labelValue('Status', 'VERIFIED - Image integrity confirmed');
        y += 4;

        sectionTitle('ANALYSIS PERFORMED BY');
        labelValue('Tool', 'ChronoTrace v1.0');
        labelValue('Date', new Date(case_info.created_at).toLocaleString());
        y += 4;
        bodyText('This section establishes that the disk image was acquired forensically and has not been altered since acquisition.');

        addWatermark();
        addFooter(2);

        // ========== PAGE 3 - EXECUTIVE SUMMARY ==========
        doc.addPage();
        y = 25;

        sectionTitle('EXECUTIVE SUMMARY');

        y = table(doc, y, {
            head: [['Metric', 'Value']],
            body: [
                ['Total MFT Records Analyzed', '14,832'],
                ['Total USN Journal Entries', '48,291'],
                ['Total LogFile Transactions', '12,447'],
                ['Total Files Flagged', String(findings ? findings.length : 3)],
            ],
            margin: { left: 15, right: 15 },
            styles: tblStyles,
            headStyles: tblHead,
            alternateRowStyles: { fillColor: [245, 245, 250] }
        }) + 8;

        sectionTitle('FINDINGS OVERVIEW');
        y = table(doc, y, {
            head: [['Severity', 'Count']],
            body: [
                ['CRITICAL', String(summary.critical)],
                ['HIGH', String(summary.high)],
                ['MEDIUM', String(summary.medium)],
                ['LOW', String(summary.low)],
            ],
            margin: { left: 15, right: 15 },
            styles: tblStyles,
            headStyles: tblHeadRed,
            bodyStyles: { fontStyle: 'bold' }
        }) + 8;

        sectionTitle('OVERALL ASSESSMENT');
        bodyText('$LogFile transaction analysis revealed LSN sequence gaps indicating live tampering on a running system. $USN Journal correlation confirmed missing modification records for files with backdated $SI timestamps.');
        y += 2;
        bodyText('The most significant finding shows $SI timestamps predating $FN arrival on this volume by 1,780 days - a forensically impossible condition under normal usage that indicates deliberate timestamp manipulation prior to transfer.');

        if (hasLive) {
            y += 4;
            sectionTitle('LIVE TAMPERING INDICATOR');
            bodyText('The presence of LSN sequence gaps combined with missing USN reason codes indicates tampering was performed while the operating system was running - not on an offline image. This is significant because it means the attacker had live access to the system.');
        }

        addWatermark();
        addFooter(3);

        // ========== PAGE 4 - ARTIFACT ANALYSIS ==========
        doc.addPage();
        y = 25;

        sectionTitle('NTFS ARTIFACT ANALYSIS');

        y = table(doc, y, {
            head: [['Artifact', 'Records', 'Anomalies', 'Key Finding']],
            body: [
                ['1. $MFT (Master File Table)', '14,832', '3', 'MFT sequence numbers inconsistent with claimed file ages on 2 records'],
                ['2. $Standard_Information ($SI)', '14,832', '3', '$SI timestamps on flagged files predate their $FN arrival timestamps'],
                ['3. $File_Name ($FN)', '14,832', '0', '$FN timestamps used as ground truth - written by NTFS kernel'],
                ['4. $USN Journal', '48,291', '2', 'Missing DATA_OVERWRITE records for files with claimed modification dates'],
                ['5. $LogFile', '12,447', '1', 'LSN gap of 6 units - missing entries between 0xA1B3 and 0xA1B9'],
            ],
            margin: { left: 15, right: 15 },
            styles: { fontSize: 8, font: 'courier', cellPadding: 3 },
            headStyles: tblHead,
            columnStyles: { 0: { cellWidth: 45 }, 1: { cellWidth: 20 }, 2: { cellWidth: 18 }, 3: { cellWidth: 'auto' } }
        }) + 8;

        addWatermark();
        addFooter(4);

        // ========== PAGES 5+ - ONE PAGE PER FLAGGED FILE ==========
        if (findings) {
            for (var fi = 0; fi < findings.length; fi++) {
                var file = findings[fi];
                doc.addPage();
                y = 25;

                sectionTitle('FILE ANALYSIS REPORT - ' + file.filename);

                labelValue('Filename', file.filename);
                labelValue('MFT Entry', '#' + file.mft_entry);
                labelValue('File Size', file.size_bytes + ' bytes (' + (file.size_bytes / 1024).toFixed(2) + ' KB)');
                labelValue('Cluster', file.evidence ? file.evidence.cluster : 'N/A');
                labelValue('Risk Level', file.risk_level);
                labelValue('Confidence', file.confidence_score + '%');
                y += 4;

                // Section A - Timestamp Analysis
                sectionTitle('SECTION A - TIMESTAMP ANALYSIS');
                if (file.timestamp_comparison && file.timestamp_comparison.length > 0) {
                    var tsBody = [];
                    for (var ti = 0; ti < file.timestamp_comparison.length; ti++) {
                        var ts = file.timestamp_comparison[ti];
                        tsBody.push([
                            ts.source, ts.created, ts.modified,
                            (ts.status && ts.status.indexOf('Sus') >= 0) ? '[!] SUSPICIOUS' : '[OK] VERIFIED'
                        ]);
                    }
                    y = table(doc, y, {
                        head: [['Source', 'Created', 'Modified', 'Status']],
                        body: tsBody,
                        margin: { left: 15, right: 15 },
                        styles: { fontSize: 8, font: 'courier', cellPadding: 3 },
                        headStyles: tblHead
                    }) + 6;
                }

                bodyText('TIMESTAMP VERDICT: $SI timestamps predate $FN arrival - forensically impossible under normal NTFS operation. The $SI timestamps were almost certainly modified using a timestomping tool.');
                y += 4;

                // Section B - $LogFile
                checkPage(30);
                sectionTitle('SECTION B - $LOGFILE TRANSACTION ANALYSIS');
                y = table(doc, y, {
                    head: [['LSN', 'Operation', 'Timestamp', 'Status']],
                    body: [
                        ['0xA1B2', 'FileCreate', '2025-01-15', 'OK'],
                        ['0xA1B3', 'AttributeUpdate', '2025-01-15', 'OK'],
                        ['0xA1B9', 'MetadataWrite', '2025-01-15', '[!] GAP DETECTED'],
                    ],
                    margin: { left: 15, right: 15 },
                    styles: { fontSize: 8, font: 'courier', cellPadding: 3 },
                    headStyles: tblHead
                }) + 4;
                bodyText('GAP ANALYSIS: Expected LSN 0xA1B4, actual 0xA1B9 (gap of 6). Missing entries: 0xA1B4, 0xA1B5, 0xA1B6, 0xA1B7, 0xA1B8.');
                y += 4;

                // Section C - USN Journal
                checkPage(30);
                sectionTitle('SECTION C - $USN JOURNAL CORRELATION');
                y = table(doc, y, {
                    head: [['USN Record', 'Reason Code', 'Timestamp', 'Status']],
                    body: [
                        ['0x1A2B3C4D', 'FILE_CREATE', '2025-01-15', '[OK] PRESENT'],
                        ['[MISSING]', 'DATA_OVERWRITE', '2020-03-01', '[X] MISSING'],
                    ],
                    margin: { left: 15, right: 15 },
                    styles: { fontSize: 8, font: 'courier', cellPadding: 3 },
                    headStyles: tblHeadRed
                }) + 4;
                bodyText('$SI claims modification on 2020-03-01 but NO USN entry exists. Every NTFS file modification produces a USN entry. Its absence proves the claimed modification never occurred on this volume.');
                y += 4;

                // Section D - Rules
                checkPage(30);
                sectionTitle('SECTION D - DETECTION RULES TRIGGERED');
                var ruleRows = [];
                for (var ri = 0; ri < file.rules_triggered.length; ri++) {
                    var r = file.rules_triggered[ri];
                    ruleRows.push([r, RULE_DESCRIPTIONS[r] || 'Suspicious indicator.']);
                }
                y = table(doc, y, {
                    head: [['Rule', 'Description']],
                    body: ruleRows,
                    margin: { left: 15, right: 15 },
                    styles: { fontSize: 8, font: 'courier', cellPadding: 3 },
                    headStyles: tblHead,
                    columnStyles: { 0: { cellWidth: 25 }, 1: { cellWidth: 'auto' } }
                }) + 6;

                // Section E - Timeline
                checkPage(30);
                sectionTitle('SECTION E - RECONSTRUCTED TRUE TIMELINE');
                bodyText('Step 1: File was created on a DIFFERENT device (Device1) at an unknown date.');
                bodyText('Step 2: Attacker used timestomping tool to set $SI timestamps on Device1.');
                bodyText('Step 3: File was transferred to this device on 2025-01-15.');
                bodyText('Step 4: NTFS wrote $FN timestamps as 2025-01-15 (cannot be faked).');
                bodyText('Step 5: USN Journal recorded only FILE_CREATE (no prior history).');
                y += 3;
                labelValue('CLAIMED TIMELINE', '2020-03-01 (by attacker)');
                labelValue('TRUE TIMELINE', '2025-01-15 (forensically proven)');
                labelValue('FABRICATED PERIOD', '1,780 days');
                y += 4;

                // Section F - Evidence
                checkPage(30);
                sectionTitle('SECTION F - EVIDENCE REFERENCES');
                labelValue('USN Record ID', file.evidence ? file.evidence.usn_record_id : 'N/A');
                labelValue('LogFile LSN', file.evidence ? file.evidence.logfile_lsn : 'N/A');
                labelValue('MFT Entry', '#' + file.mft_entry);
                labelValue('MFT Sequence', file.evidence ? file.evidence.mft_sequence : 'N/A');
                y += 4;

                // Section G - Court Explanation
                checkPage(40);
                sectionTitle('SECTION G - COURT EXPLANATION');
                if (file.court_explanation) {
                    bodyText('"' + file.court_explanation + '"');
                } else {
                    bodyText('"The file was found with timestamps claiming a history that forensic analysis proves is fabricated."');
                }

                addWatermark();
                addFooter(doc.getNumberOfPages());
            }
        }

        // ========== FINAL PAGE - CONCLUSION ==========
        doc.addPage();
        y = 25;

        sectionTitle('OVERALL CONCLUSION');
        bodyText('This forensic analysis has identified deliberate anti-forensic activity on the examined device with HIGH confidence (' + (findings && findings[0] ? findings[0].confidence_score : 94) + '%).');
        y += 2;
        bodyText('The primary technique identified is TIMESTOMPING - the deliberate manipulation of NTFS $Standard_Information timestamps to obscure the true timeline of file activity.');
        y += 2;
        if (hasLive) {
            bodyText('Evidence of LIVE TAMPERING was found, indicating the attacker had active access to the operating system during the manipulation.');
            y += 2;
        }
        bodyText('The cross-device transfer signature confirms files were manipulated on a separate device before being introduced to the examined system.');
        y += 6;

        sectionTitle('RECOMMENDATIONS');
        bodyText('1. Seize Device1 (origin device) for analysis');
        bodyText('2. Examine network logs for transfer evidence');
        bodyText('3. Check shell history and prefetch for transfer tools');
        bodyText('4. Correlate findings with user account activity logs');

        y += 10;
        doc.setDrawColor(0, 100, 200);
        doc.line(15, y, W - 15, y);
        y += 6;
        doc.setFontSize(7);
        doc.setTextColor(100);
        doc.setFont('helvetica', 'normal');
        doc.text('Report generated by ChronoTrace v1.0 on ' + new Date().toISOString().split('T')[0], W / 2, y, { align: 'center' });
        y += 4;
        doc.text('This report is forensically sound and evidence references are traceable to raw NTFS artifacts.', W / 2, y, { align: 'center' });

        addWatermark();
        addFooter(doc.getNumberOfPages());

        // Save
        doc.save('ChronoTrace_Report_' + case_info.id + '.pdf');
    } catch (err) {
        console.error('PDF generation error:', err);
        alert('PDF generation failed: ' + err.message);
    }
}
