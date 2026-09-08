# MyApp — Event Taxonomy

## Login

### login_screen_input_email_entered
- **Trigger:** User enters value in Input/Email
- **Source:** Figma node `1:10`
- **Properties:**
  - `field_name` (string) — Name of the input field
  - `is_valid` (boolean) — Whether the input passed validation
  - `screen_name` (string) — Screen where event occurred
  - `platform` (string) (enum: ios, android, web)
  - `app_version` (string) — Application version

### login_screen_input_password_entered
- **Trigger:** User enters value in Input/Password
- **Source:** Figma node `1:12`
- **Properties:**
  - `field_name` (string) — Name of the input field
  - `is_valid` (boolean) — Whether the input passed validation
  - `screen_name` (string) — Screen where event occurred
  - `platform` (string) (enum: ios, android, web)
  - `app_version` (string) — Application version

### login_screen_log_in_clicked
- **Trigger:** User clicks Log In
- **Source:** Figma node `1:14`
- **Properties:**
  - `element_text` (string) — Visible text of the clicked element
  - `screen_name` (string) — Screen where event occurred
  - `platform` (string) (enum: ios, android, web)
  - `app_version` (string) — Application version

### login_screen_forgot_password_clicked
- **Trigger:** User clicks Forgot password?
- **Source:** Figma node `1:16`
- **Properties:**
  - `element_text` (string) — Visible text of the clicked element
  - `screen_name` (string) — Screen where event occurred
  - `platform` (string) (enum: ios, android, web)
  - `app_version` (string) — Application version

### login_screen_remember_me_toggled
- **Trigger:** User toggles Remember me
- **Source:** Figma node `1:20`
- **Properties:**
  - `screen_name` (string) — Screen where event occurred
  - `platform` (string) (enum: ios, android, web)
  - `app_version` (string) — Application version

### login_screen_pageview
- **Trigger:** User views login screen screen
- **Properties:**
  - `screen_name` (string) — Screen where event occurred
  - `platform` (string) (enum: ios, android, web)
  - `app_version` (string) — Application version

## Home

### home_account_balance_viewed
- **Trigger:** User views Account Balance
- **Source:** Figma node `2:10`
- **Properties:**
  - `screen_name` (string) — Screen where event occurred
  - `platform` (string) (enum: ios, android, web)
  - `app_version` (string) — Application version

### home_transfer_clicked
- **Trigger:** User clicks Transfer
- **Source:** Figma node `2:12`
- **Properties:**
  - `element_text` (string) — Visible text of the clicked element
  - `screen_name` (string) — Screen where event occurred
  - `platform` (string) (enum: ios, android, web)
  - `app_version` (string) — Application version

### home_pay_bills_clicked
- **Trigger:** User clicks Pay Bills
- **Source:** Figma node `2:14`
- **Properties:**
  - `element_text` (string) — Visible text of the clicked element
  - `screen_name` (string) — Screen where event occurred
  - `platform` (string) (enum: ios, android, web)
  - `app_version` (string) — Application version

### home_accounts_viewed
- **Trigger:** User views Accounts
- **Source:** Figma node `2:16`
- **Properties:**
  - `screen_name` (string) — Screen where event occurred
  - `platform` (string) (enum: ios, android, web)
  - `app_version` (string) — Application version

### home_cards_viewed
- **Trigger:** User views Cards
- **Source:** Figma node `2:18`
- **Properties:**
  - `screen_name` (string) — Screen where event occurred
  - `platform` (string) (enum: ios, android, web)
  - `app_version` (string) — Application version

### home_bottom_nav_clicked
- **Trigger:** User clicks BottomNav
- **Source:** Figma node `2:20`
- **Properties:**
  - `element_text` (string) — Visible text of the clicked element
  - `screen_name` (string) — Screen where event occurred
  - `platform` (string) (enum: ios, android, web)
  - `app_version` (string) — Application version

### home_pageview
- **Trigger:** User views home screen
- **Properties:**
  - `screen_name` (string) — Screen where event occurred
  - `platform` (string) (enum: ios, android, web)
  - `app_version` (string) — Application version

## Payments

### payment_form_amount_entered
- **Trigger:** User enters value in Amount
- **Source:** Figma node `3:10`
- **Properties:**
  - `field_name` (string) — Name of the input field
  - `is_valid` (boolean) — Whether the input passed validation
  - `screen_name` (string) — Screen where event occurred
  - `platform` (string) (enum: ios, android, web)
  - `app_version` (string) — Application version

### payment_form_select_account_selected
- **Trigger:** User selects from Select Account
- **Source:** Figma node `3:12`
- **Properties:**
  - `screen_name` (string) — Screen where event occurred
  - `platform` (string) (enum: ios, android, web)
  - `app_version` (string) — Application version

### payment_form_save_recipient_checked
- **Trigger:** User checks Save recipient
- **Source:** Figma node `3:14`
- **Properties:**
  - `screen_name` (string) — Screen where event occurred
  - `platform` (string) (enum: ios, android, web)
  - `app_version` (string) — Application version

### payment_form_send_payment_clicked
- **Trigger:** User clicks Send Payment
- **Source:** Figma node `3:16`
- **Properties:**
  - `element_text` (string) — Visible text of the clicked element
  - `screen_name` (string) — Screen where event occurred
  - `platform` (string) (enum: ios, android, web)
  - `app_version` (string) — Application version

### payment_form_interactive_frame_clicked
- **Trigger:** User clicks InteractiveFrame
- **Source:** Figma node `3:18`
- **Properties:**
  - `element_text` (string) — Visible text of the clicked element
  - `screen_name` (string) — Screen where event occurred
  - `platform` (string) (enum: ios, android, web)
  - `app_version` (string) — Application version

### payment_success_done_clicked
- **Trigger:** User clicks Done
- **Source:** Figma node `3:20`
- **Properties:**
  - `element_text` (string) — Visible text of the clicked element
  - `screen_name` (string) — Screen where event occurred
  - `platform` (string) (enum: ios, android, web)
  - `app_version` (string) — Application version

### payment_form_pageview
- **Trigger:** User views payment form screen
- **Properties:**
  - `screen_name` (string) — Screen where event occurred
  - `platform` (string) (enum: ios, android, web)
  - `app_version` (string) — Application version

### payment_success_pageview
- **Trigger:** User views payment success screen
- **Properties:**
  - `screen_name` (string) — Screen where event occurred
  - `platform` (string) (enum: ios, android, web)
  - `app_version` (string) — Application version
