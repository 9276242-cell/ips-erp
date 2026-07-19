import ftplib
import os
import urllib.request
import urllib.parse
import json
import ssl
import sys
import io

PHP_MAILER_CODE = """<?php
header('Content-Type: application/json');

if ($_SERVER['REQUEST_METHOD'] !== 'POST') {
    echo json_encode(["success" => false, "error" => "Only POST allowed"]);
    exit;
}

$secret = $_POST['secret'] ?? '';
if ($secret !== 'HITS_FastCloud_Mail_Secret_2026') {
    echo json_encode(["success" => false, "error" => "Unauthorized"]);
    exit;
}

$to = $_POST['to'] ?? '';
$subject = $_POST['subject'] ?? '';
$body = $_POST['body'] ?? '';
$from = $_POST['from'] ?? 'info@khanwco.net';
$cc = $_POST['cc'] ?? '';
$bcc = $_POST['bcc'] ?? '';

if (empty($to) || empty($subject) || empty($body)) {
    echo json_encode(["success" => false, "error" => "Missing required fields"]);
    exit;
}

define('WP_USE_THEMES', false);
if (file_exists('wp-load.php')) {
    require_once('wp-load.php');
} else {
    echo json_encode(["success" => false, "error" => "wp-load.php not found"]);
    exit;
}

require_once ABSPATH . WPINC . '/PHPMailer/PHPMailer.php';
require_once ABSPATH . WPINC . '/PHPMailer/SMTP.php';
require_once ABSPATH . WPINC . '/PHPMailer/Exception.php';

$mail = new PHPMailer\\PHPMailer\\PHPMailer(true);

try {
    $mail->CharSet = 'UTF-8';
    $mail->isSMTP();
    $mail->Host       = '127.0.0.1';
    $mail->SMTPAuth   = true;
    $mail->Username   = 'info@khanwco.net';
    $mail->Password   = 'AmeenMail2026!';
    $mail->Port       = 587;
    $mail->SMTPSecure = '';
    $mail->SMTPAutoTLS = false;

    $mail->setFrom($from, 'Hamayun IT Solutions (HITS)');
    $mail->addAddress($to);

    if (!empty($cc)) {
        foreach (explode(',', $cc) as $c) {
            if (trim($c) !== "") {
                $mail->addCC(trim($c));
            }
        }
    }

    if (!empty($bcc)) {
        foreach (explode(',', $bcc) as $b) {
            if (trim($b) !== "") {
                $mail->addBCC(trim($b));
            }
        }
    }

    $mail->isHTML(true);
    $mail->Subject = $subject;
    $mail->Body    = $body;

    $mail->send();
    echo json_encode(["success" => true]);
} catch (Exception $e) {
    try {
        $mail->Port = 25;
        $mail->send();
        echo json_encode(["success" => true, "note" => "Sent via Port 25"]);
    } catch (Exception $e2) {
        echo json_encode(["success" => false, "error" => "Port 587 error: " . $mail->ErrorInfo . " | Port 25 error: " . $mail->ErrorInfo]);
    }
}
?>"""

def upload_mailer_php():
    try:
        ftp = ftplib.FTP('162.244.93.2')
        ftp.login('khanwcocom', 'm-@EhU7mgC2L05')
        ftp.cwd('domains/khanwco.net/public_html')
        
        php_file = io.BytesIO(PHP_MAILER_CODE.encode('utf-8'))
        ftp.storbinary('STOR wp_send_mail.php', php_file)
        ftp.quit()
        return True
    except Exception as e:
        print(f"FTP Upload Failed: {e}")
        return False

def delete_mailer_php():
    try:
        ftp = ftplib.FTP('162.244.93.2')
        ftp.login('khanwcocom', 'm-@EhU7mgC2L05')
        ftp.cwd('domains/khanwco.net/public_html')
        ftp.delete('wp_send_mail.php')
        ftp.quit()
        return True
    except Exception as e:
        print(f"FTP Deletion Failed: {e}")
        return False

def send_via_fastcloud(to_email, subject, body_html, cc_emails="", bcc_emails="", from_email="info@khanwco.net"):
    url = "https://khanwco.net/wp_send_mail.php"
    post_data = {
        'secret': 'HITS_FastCloud_Mail_Secret_2026',
        'to': to_email,
        'subject': subject,
        'body': body_html,
        'from': from_email,
        'cc': cc_emails,
        'bcc': bcc_emails
    }
    
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    
    data = urllib.parse.urlencode(post_data).encode('utf-8')
    req = urllib.request.Request(url, data=data, method='POST')
    
    try:
        with urllib.request.urlopen(req, context=ctx) as response:
            res_body = response.read().decode('utf-8')
            res_json = json.loads(res_body)
            if res_json.get("success"):
                print(f"Successfully sent email to {to_email}")
                return True
            else:
                print(f"Failed to send to {to_email}: {res_json.get('error')}")
                return False
    except Exception as e:
        print(f"Request failed for {to_email}: {e}")
        return False

def main():
    recipient = "abdur.rub.khan@gmail.com"
    cc_recipients = "9276242@gmail.com,abdur_rub_khan@hotmail.com"
    bcc_recipients = "inam.jaffery@gmail.com,emad@tahoortechnologies.com,mohammademad@gmail.com,hamayun.its@gmail.com,mibrahim1995@gmail.com,zubairomaransari1100@gmail.com,Zubair.omar.ansari@hotmail.co"
    from_email = "info@khanwco.net"
    
    # Large, detailed HTML Body with flowcharts and explanations
    body_html = """<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>IPS ERP Proposal & Technical Architecture</title>
</head>
<body style="font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background-color: #f8fafc; color: #334155; margin: 0; padding: 0;">
    <div style="max-width: 800px; margin: 40px auto; background: #ffffff; border-radius: 16px; box-shadow: 0 4px 30px rgba(0,0,0,0.04); overflow: hidden; border: 1px solid #e2e8f0;">
        
        <!-- HEADER -->
        <div style="background: linear-gradient(135deg, #065f46 0%, #047857 50%, #0f172a 100%); padding: 40px 30px; text-align: center; color: #ffffff;">
            <div style="display: inline-block; padding: 8px 16px; background-color: rgba(255,255,255,0.15); border-radius: 20px; font-size: 11px; font-weight: bold; letter-spacing: 1px; margin-bottom: 12px; text-transform: uppercase;">
                Commercial Proposal & Staging Showcase
            </div>
            <h1 style="margin: 0; font-size: 24px; font-weight: 800; letter-spacing: -0.5px; line-height: 1.2;">
                IPS ENTERPRISE RESOURCE PLANNING (ERP)
            </h1>
            <p style="margin: 10px 0 0 0; font-size: 14px; opacity: 0.9;">
                Turn-key Accounting, Inventory FIFO POS, & Library Circulation Management
            </p>
        </div>

        <div style="padding: 35px 30px; line-height: 1.7; font-size: 14px;">
            
            <!-- GREETING & INTRO -->
            <p style="margin-top: 0; font-size: 15px;">Dear Abdur Rab Khan,</p>
            <p>
                We are pleased to submit the complete, turn-key technical implementation proposal and live showcase for the <strong>Institute of Policy Studies (IPS) ERP & Financial Portal</strong>. Designed as an institutional-grade accounting, sales cataloging, and library circulation platform, this system is now fully coded, verified, and running live on our serverless Google Cloud Run infrastructure for your immediate testing and validation.
            </p>

            <!-- INTERACTIVE BUTTONS & DEMO ACCESS -->
            <div style="margin: 30px 0; background-color: #f0fdf4; border: 1px solid #bbf7d0; border-radius: 12px; padding: 25px; text-align: center;">
                <h3 style="margin-top: 0; color: #166534; font-size: 16px; font-weight: 700;">🌐 LIVE ERP DEMO PORTAL</h3>
                <p style="font-size: 13px; color: #1e3f20; margin-bottom: 20px;">
                    Access the deployed staging system, switch styling themes in real-time, perform transactions, and generate statements:
                </p>
                
                <div style="margin-bottom: 20px;">
                    <a href="https://ips-erp-897055767918.us-central1.run.app/" target="_blank" style="background-color: #059669; color: #ffffff; padding: 12px 30px; border-radius: 8px; font-weight: bold; font-size: 14px; text-decoration: none; display: inline-block; box-shadow: 0 4px 10px rgba(5,150,105,0.2);">
                        Launch Live IPS ERP
                    </a>
                </div>

                <div style="display: inline-block; text-align: left; background-color: #ffffff; border: 1px solid #dcfce7; border-radius: 8px; padding: 15px; font-size: 12px; color: #1e293b; width: 100%; box-sizing: border-box;">
                    <div style="font-weight: 700; color: #166534; margin-bottom: 8px; text-align: center;">🔑 Quick Demo Credentials (Clickable in UI)</div>
                    <div style="display: flex; justify-content: space-between; margin-bottom: 4px;">
                        <span><strong>Director / Admin:</strong> <code>admin</code> / <code>admin123</code></span>
                        <span><strong>Librarian:</strong> <code>librarian</code> / <code>admin123</code></span>
                    </div>
                    <div style="display: flex; justify-content: space-between;">
                        <span><strong>Accountant:</strong> <code>accountant</code> / <code>admin123</code></span>
                        <span><strong>Book Customer (Visitor):</strong> <code>visitor</code> / <code>admin123</code></span>
                    </div>
                </div>
                
                <div style="margin-top: 15px;">
                    <a href="https://github.com/9276242-cell/ips-erp" target="_blank" style="color: #047857; text-decoration: none; font-weight: bold; font-size: 12px;">
                        📂 View GitHub Repository &rarr;
                    </a>
                </div>
            </div>

            <!-- SECTION 1: ARCHITECTURE FLOWCHART -->
            <div style="font-size: 16px; font-weight: bold; color: #0f172a; border-left: 4px solid #059669; padding-left: 10px; margin-top: 35px; margin-bottom: 15px;">
                1. MODULE INTEGRATION & SYSTEM FLOWCHART
            </div>
            <p>
                The system relies on a unified ledger schema where peripheral activity (Book POS sales, library loan fines, and staff payruns) generates double-entry entries to ledger accounts, which instantly cascade into the Trial Balance and P&L statements.
            </p>
            
            <!-- FLOWCHART HTML BOXES -->
            <div style="background-color: #f8fafc; border: 1px solid #e2e8f0; border-radius: 8px; padding: 20px; font-family: monospace; font-size: 12px; line-height: 1.5; color: #1e293b; margin-bottom: 25px;">
                <div style="text-align:center; font-weight:bold; color: #047857; margin-bottom: 10px;">[ IPS SYSTEM TRANSACTION FLOW ]</div>
                <div style="border: 1.5px solid #cbd5e1; padding: 8px; border-radius: 4px; background: #ffffff; text-align: center; font-weight: bold;">
                    USER INTERFACE (Tailwind SPA / Local HTML5)
                </div>
                <div style="text-align: center; padding: 5px 0; font-weight: bold; color: #64748b;">↓ (JWT Encrypted REST API Calls)</div>
                <div style="border: 1.5px solid #cbd5e1; padding: 8px; border-radius: 4px; background: #ffffff; text-align: center; font-weight: bold;">
                    FASTAPI GATEWAY & ROLE MIDDLEWARE
                </div>
                <div style="text-align: center; padding: 5px 0; font-weight: bold; color: #64748b;">↓ (Double-Entry Core Processing Engine)</div>
                
                <div style="display: flex; gap: 8px; justify-content: space-between;">
                    <div style="flex: 1; border: 1px solid #bbf7d0; padding: 6px; border-radius: 4px; background: #f0fdf4; text-align: center; font-size: 10px;">
                        <b>POS Sales Module</b><br>FIFO Stock Card<br>➔ DB Debit / Credit
                    </div>
                    <div style="flex: 1; border: 1px solid #bae6fd; padding: 6px; border-radius: 4px; background: #f0f9ff; text-align: center; font-size: 10px;">
                        <b>Library Circulation</b><br>Accession Log<br>➔ Fine Receivables
                    </div>
                    <div style="flex: 1; border: 1px solid #fef08a; padding: 6px; border-radius: 4px; background: #fefce8; text-align: center; font-size: 10px;">
                        <b>Fixed Assets</b><br>Capitalize Costs<br>➔ StraightLine WDV
                    </div>
                    <div style="flex: 1; border: 1px solid #fed7aa; padding: 6px; border-radius: 4px; background: #fff7ed; text-align: center; font-size: 10px;">
                        <b>HR & Payroll</b><br>Allowances/Deductions<br>➔ Salary Expense
                    </div>
                </div>
                
                <div style="text-align: center; padding: 5px 0; font-weight: bold; color: #64748b;">↓ (Aggregated Ledger Journal Posting)</div>
                <div style="border: 1.5px solid #cbd5e1; padding: 8px; border-radius: 4px; background: #ffffff; text-align: center; font-weight: bold;">
                    SQLITE TRANSACTIONAL ENGINE (ACID Compliant DB)
                </div>
                <div style="text-align: center; padding: 5px 0; font-weight: bold; color: #64748b;">↓ (Instantly Renders Statements)</div>
                <div style="background-color: #f1f5f9; border: 1.5px dashed #cbd5e1; padding: 8px; border-radius: 4px; text-align: center; font-weight: bold; color: #047857;">
                    Trial Balance ➔ Income & Expense (P&L) ➔ Balance Sheet ➔ GL Ledger SOA
                </div>
            </div>

            <!-- SECTION 2: MODULE EXPLANATIONS -->
            <div style="font-size: 16px; font-weight: bold; color: #0f172a; border-left: 4px solid #059669; padding-left: 10px; margin-top: 35px; margin-bottom: 15px;">
                2. EXPLAINING KEY FUNCTIONAL MODULES
            </div>
            <p>
                Each module is engineered to operate on real double-entry accounting records, eliminating mock summaries. Here's how the modules operate:
            </p>
            <ul>
                <li><strong>Financial Core & Fund Accounting:</strong> Enforces standard bookkeeping constraints. Every voucher (Payment, Receipt, Journal) requires Debits = Credits. Accounts are structured to track restricted donor funds (e.g., Zakat, HEC grants) separately from general unrestricted operating capital.</li>
                <li><strong>FIFO Sales & Inventory Control:</strong> Features a full POS checkout desk. When publications are sold, stock is depleted dynamically using First-In-First-Out (FIFO) stock card batches. The cost of goods sold (COGS) is calculated, debited to printing expenses, and credited to inventory assets.</li>
                <li><strong>Library Circulation & Member Desk:</strong> Catalogs library books with unique accession numbers. It tracks loans, due dates, returns, and automatically calculates overdue fines, instantly posting the fine receipt to the general ledger upon payment.</li>
                <li><strong>HR Payroll & Salary Disbursements:</strong> Supports full payrun processing. Accountants specify allowances and deductions, calculate net payouts, and trigger the disbursement voucher, generating a printable payslip layout.</li>
                <li><strong>Fixed Assets Capitalization:</strong> Automatically logs assets at cost price (debiting fixed assets, crediting bank) and calculates depreciation at standard annual rates using the Straight-Line method.</li>
            </ul>

            <!-- SECTION 3: USER ROLES FLOW & WALKTHROUGH -->
            <div style="font-size: 16px; font-weight: bold; color: #0f172a; border-left: 4px solid #059669; padding-left: 10px; margin-top: 35px; margin-bottom: 15px;">
                3. ROLE-BASED WORKFLOWS & TESTING PATHS
            </div>
            <p>
                Testing is streamlined by selecting predefined roles. Different personnel see views suited for their operational needs:
            </p>
            
            <div style="background-color: #f8fafc; border: 1px solid #e2e8f0; border-radius: 8px; padding: 20px; font-family: monospace; font-size: 12px; line-height: 1.5; color: #1e293b; margin-bottom: 20px;">
                <div style="text-align:center; font-weight:bold; color: #ca8a04; margin-bottom: 10px;">[ ROLE PERMISSIONS SEGREGATION ]</div>
                ADMIN (Director)  ➔ Full Access: Read/Write All Modules & Immutable Audit Trails<br>
                ACCOUNTANT       ➔ Financial Core, General Ledger, Fixed Assets, & Payroll<br>
                LIBRARIAN        ➔ Catalog Registry, Member Desk, Book Issue/Return Loans<br>
                SALES DESK       ➔ POS Terminal Sales, Stock Restocking & Inventory Catalog<br>
                VISITOR          ➔ Book Catalog E-Shop Shopping Cart & Order Checkout only
            </div>

            <h4 style="color: #0f172a; font-size: 14px; margin-bottom: 5px;">Step-by-Step Testing Roadmap:</h4>
            <ol>
                <li><strong>Log in as Accountant:</strong> Go to the Financial Core and inspect the default Trial Balance. Click <em>"New Voucher Entry"</em>, create a Journal Voucher (JV), Debit Rent Expense 10,000, and Credit Cash at Hand 10,000. Verify the balance changes on the Trial Balance instantly.</li>
                <li><strong>Log in as Sales Desk:</strong> Open the POS tab. Add 2 units of the <em>China-Pakistan Economic Corridor (CPEC) Report</em> to the cart. Complete checkout under Cash. Switch back to the Accountant view and observe that Book Sales Income (4003) has increased by 2,200 PKR.</li>
                <li><strong>Log in as Librarian:</strong> Issue the book <em>"Pakistan: Beyond the Crisis State"</em> to Dr. Anis Ahmad. Confirm the book status changes to "Borrowed". Return the book and check for fines.</li>
                <li><strong>Log in as Admin:</strong> Run the annual depreciation under Fixed Assets. Inspect the Audit Trails tab to see a complete, tamper-proof listing of every action taken by each username.</li>
            </ol>

            <!-- SECTION 4: THE VISITOR EXPERIENCE -->
            <div style="font-size: 16px; font-weight: bold; color: #0f172a; border-left: 4px solid #059669; padding-left: 10px; margin-top: 35px; margin-bottom: 15px;">
                4. THE VISITOR SHOPPING EXPERIENCE & SELF-SERVICE
            </div>
            <p>
                To demonstrate commercial readiness to the board, we developed a simplified, public-facing **E-Shop experience** for visitor accounts.
            </p>
            
            <div style="background-color: #f8fafc; border: 1px solid #e2e8f0; border-radius: 8px; padding: 20px; font-family: monospace; font-size: 12px; line-height: 1.5; color: #1e293b; margin-bottom: 25px;">
                <div style="text-align:center; font-weight:bold; color: #4f46e5; margin-bottom: 10px;">[ VISITOR E-SHOP PROCESS ]</div>
                Visitor Logs In ➔ View IPS Press Catalog ➔ Add Books to Shopping Cart ➔<br>
                Adjust Quantities ➔ Select Payment Method ➔ Click Checkout ➔<br>
                [System Depletes FIFO Stock + Posts Sales Ledger JV + Updates P&L Real-Time]
            </div>
            <p>
                Logging in as a <code>Visitor</code> hides all backend data (ledgers, payrolls, audit trails) and displays only the **IPS Press E-Shop**. Visitors can add publications to their shopping cart and complete checkouts. This triggers immediate FIFO stock depletion and logs the sales revenue, letting you show the board a full transaction cycle starting from a public customer purchase down to the general ledger balance sheet.
            </p>

            <!-- SECTION 5: GENERAL LEDGER SOA REPORTING -->
            <div style="font-size: 16px; font-weight: bold; color: #0f172a; border-left: 4px solid #059669; padding-left: 10px; margin-top: 35px; margin-bottom: 15px;">
                5. DYNAMIC GENERAL LEDGER & STATEMENT OF ACCOUNT (SOA)
            </div>
            <p>
                We have added a professional-grade **Statement of Account (SOA)** panel in the Financial Core:
            </p>
            <ul>
                <li><strong>Opening Balance Tracking:</strong> By entering a start date, the system aggregates all historical transactions prior to that date to calculate the correct opening balance.</li>
                <li><strong>Running Balance Ledger:</strong> Columns list the transaction date, voucher number, type, narration line-by-line, and recalculate the running balance dynamically based on debit/credit rules.</li>
                <li><strong>Printable Statements:</strong> Clicking <em>"Print SOA"</em> launches a clean print-ready layout containing official header details, physical addresses, phone contacts, signature fields, and transaction rows.</li>
            </ul>

            <!-- CLOSING PARAGRAPH -->
            <p style="margin-top: 25px;">
                This staging system demonstrates a high level of design, workflow security, and functional completeness. We are prepared to assist you in executing this demonstration for the IPS board and look forward to your valuable feedback.
            </p>
            
            <div style="margin-top: 35px; margin-bottom: 5px; font-size: 14px;">Sincerely,</div>
            <div style="margin-top: 5px; margin-bottom: 5px; font-size: 16px; font-weight: 800; color: #065f46;">Ameen Mahmood</div>
            <div style="margin-top: 0; margin-bottom: 25px; font-size: 13px; font-weight: 600; color: #64748b;">Director Business Solutions & Senior Architect</div>
            
            <!-- CONTACT SIGNATURE FOOTER -->
            <div style="border-top: 1px solid #e2e8f0; margin-top: 30px; padding-top: 20px; font-size: 12px; line-height: 1.7; color: #475569;">
                <span style="font-size: 14px; font-weight: bold; color: #065f46; display: block; margin-bottom: 6px;">Hamayun IT Solutions (HITS)</span>
                <b>Headquarters:</b> RIYADH OFFICE (KSA), Street # 28, Al Olaya District, Riyadh, Saudi Arabia<br>
                <b>Email Support:</b> ceo@khanwco.net / info@khanwco.net<br>
                <b>Corporate Portal:</b> <a href="https://hits-ksa.com" target="_blank" style="color: #047857; text-decoration: none; font-weight: bold;">hits-ksa.com</a><br>
                <b>Direct WhatsApp:</b> +966 54 042 3544<br>
                <b>Islamabad Branch:</b> Nasr Chambers, 1, MPCHS Commercial, E-11/3, Islamabad, Pakistan
            </div>
        </div>
        
        <!-- FOOTER -->
        <div style="background-color: #f1f5f9; padding: 25px; text-align: center; border-top: 1px solid #e2e8f0; font-size: 11px; color: #64748b;">
            <p style="margin: 0; font-weight: 600;">&copy; 2026 Hamayun IT Solutions (HITS) Riyadh Headquarters, KSA. All rights reserved.</p>
        </div>
    </div>
</body>
</html>"""

    if not upload_mailer_php():
        sys.exit(1)
        
    try:
        print(f"Sending IPS ERP Technical Proposal email to {recipient}...")
        res = send_via_fastcloud(
            to_email=recipient,
            subject="Turn-key IPS ERP: Complete Accounting, Inventory POS & Library Management Proposal",
            body_html=body_html,
            cc_emails=cc_recipients,
            bcc_emails=bcc_recipients,
            from_email=from_email
        )
        if res:
            print("Email sent successfully!")
        else:
            print("Email delivery failed.")
    finally:
        delete_mailer_php()

if __name__ == "__main__":
    main()
