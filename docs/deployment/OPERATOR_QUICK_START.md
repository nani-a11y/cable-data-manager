# Cable Data Manager — Operator Quick Start & Daily Guide

**Target User:** Cable TV Operator / Counter Cashier  
**Purpose:** Simple, plain-language operating instructions for daily shop operations.

---

## 1. How to Open and Use the Software

1. **Turn on the computer and log into the desktop.**
2. **Open Google Chrome (or Firefox / Edge).**
3. **Click your browser bookmark** or type the address:
   ```text
   http://localhost:8080
   ```
4. **Log in:**
   - Enter your email address and password.
   - Click **Log In**.

---

## 2. Daily Workflow

### Recording a Customer Payment:
1. Search for the customer using their **Name**, **Mobile Number**, or **Setup Box Number**.
2. Click **View / Record Payment**.
3. Enter the cash or UPI amount received.
4. Select the payment mode (**Cash** or **UPI**).
5. Click **Record Payment**.
6. The screen immediately updates the customer's Khata (passbook), showing their remaining due or advance balance.

### Checking Today's Collections:
1. Click **Reports** or **Monthly Register** in the top navigation bar.
2. Select the current month.
3. Review total collections, cash collected, and UPI totals.

---

## 3. What to Do After a Power Cut

The software is configured to start automatically whenever the computer turns on.
1. When power returns, turn on the computer.
2. Wait 1 minute for background services to load.
3. Open your browser and go to `http://localhost:8080`.
4. If the page does not open immediately, wait 30 seconds and refresh.

---

## 4. How Backups Work (Do Not Touch the Backup Drive!)

- The software automatically creates an encrypted backup every night at **2:00 AM**.
- Backups are saved to the **black external USB drive** attached to the back of the computer.
- **Rule:** Keep the external USB drive plugged in at all times.
- If the external drive is accidentally unplugged, plug it back into the same USB slot immediately.

### How to Check if Backups are Working:
Click the desktop shortcut **"Check Backup Status"** (or ask the technical administrator). If the status says **"MOUNTED (OK)"**, your data is protected.

---

## 5. Troubleshooting & Support

| Problem | Cause | What You Should Do |
| :--- | :--- | :--- |
| **"Unable to connect" or white page** | Software starting up or computer just rebooted | Wait 1 minute and click Refresh in the browser. |
| **"Invalid Email or Password"** | Typo or caps lock is on | Check keyboard caps lock; re-type password carefully. |
| **Backup status warning** | External USB drive unplugged | Check that the external USB drive cable is firmly plugged in. |
| **Computer running very slow** | Disk full or background update | Restart the computer cleanly. |

**For Technical Support:**  
Contact your technical administrator or maintenance engineer.
