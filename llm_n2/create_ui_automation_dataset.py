"""Create UI Test Automation Dataset
Focus on UI interactions only - Click, Enter, Navigate, Verify, Select, etc.
NO programming or implementation steps.
"""
import json

# UI Test Automation Examples - Only UI interactions
ui_automation_examples = [
    # Login/Authentication
    {
        "instruction": "login with username and password",
        "output": "Step 1: Navigate to login page. Step 2: Locate username field. Step 3: Click username field. Step 4: Enter username. Step 5: Locate password field. Step 6: Click password field. Step 7: Enter password. Step 8: Click login button. Step 9: Verify successful login."
    },
    {
        "instruction": "login to Gmail",
        "output": "Step 1: Open Gmail website. Step 2: Click Sign In button. Step 3: Enter email address. Step 4: Click Next button. Step 5: Enter password. Step 6: Click Next button. Step 7: Verify inbox page loads."
    },
    {
        "instruction": "login to Facebook",
        "output": "Step 1: Navigate to Facebook homepage. Step 2: Locate email field. Step 3: Enter email address. Step 4: Locate password field. Step 5: Enter password. Step 6: Click Log In button. Step 7: Verify News Feed appears."
    },
    {
        "instruction": "sign in to Microsoft account",
        "output": "Step 1: Open Microsoft login page. Step 2: Enter email or phone number. Step 3: Click Next. Step 4: Enter password. Step 5: Click Sign in. Step 6: Verify account dashboard loads."
    },
    {
        "instruction": "logout from account",
        "output": "Step 1: Locate profile icon. Step 2: Click profile menu. Step 3: Select Logout option. Step 4: Click Confirm if prompted. Step 5: Verify redirect to login page."
    },
    
    # E-commerce
    {
        "instruction": "search for a product on Amazon",
        "output": "Step 1: Open Amazon homepage. Step 2: Locate search bar. Step 3: Click search field. Step 4: Enter product name. Step 5: Click search icon or press Enter. Step 6: Verify search results page loads."
    },
    {
        "instruction": "add item to shopping cart",
        "output": "Step 1: Navigate to product page. Step 2: Select quantity dropdown. Step 3: Choose desired quantity. Step 4: Click Add to Cart button. Step 5: Verify item added confirmation message. Step 6: Close popup if present."
    },
    {
        "instruction": "checkout and place order",
        "output": "Step 1: Click shopping cart icon. Step 2: Review cart items. Step 3: Click Proceed to Checkout button. Step 4: Enter shipping address. Step 5: Click Continue. Step 6: Select payment method. Step 7: Enter payment details. Step 8: Click Place Order button. Step 9: Verify order confirmation page."
    },
    {
        "instruction": "filter products by price range",
        "output": "Step 1: Navigate to category page. Step 2: Locate price filter section. Step 3: Enter minimum price. Step 4: Enter maximum price. Step 5: Click Apply or Go button. Step 6: Verify filtered results display."
    },
    {
        "instruction": "sort products by rating",
        "output": "Step 1: Locate sort dropdown. Step 2: Click sort options. Step 3: Select Customer Rating. Step 4: Verify products reorder by rating."
    },
    
    # Form Filling
    {
        "instruction": "fill out registration form",
        "output": "Step 1: Navigate to registration page. Step 2: Enter first name. Step 3: Enter last name. Step 4: Enter email address. Step 5: Enter phone number. Step 6: Create password. Step 7: Confirm password. Step 8: Select country from dropdown. Step 9: Check terms checkbox. Step 10: Click Submit button."
    },
    {
        "instruction": "submit contact form",
        "output": "Step 1: Navigate to contact page. Step 2: Enter full name. Step 3: Enter email address. Step 4: Enter subject. Step 5: Enter message in text area. Step 6: Click Send button. Step 7: Verify success message appears."
    },
    {
        "instruction": "fill out job application",
        "output": "Step 1: Open job posting. Step 2: Click Apply Now button. Step 3: Upload resume file. Step 4: Enter personal information. Step 5: Enter work experience. Step 6: Enter education details. Step 7: Answer screening questions. Step 8: Click Submit Application. Step 9: Verify confirmation message."
    },
    
    # Navigation
    {
        "instruction": "navigate to settings page",
        "output": "Step 1: Locate profile or menu icon. Step 2: Click menu. Step 3: Select Settings option. Step 4: Verify settings page loads."
    },
    {
        "instruction": "open help center",
        "output": "Step 1: Scroll to page footer. Step 2: Locate Help or Support link. Step 3: Click Help link. Step 4: Verify help center opens."
    },
    {
        "instruction": "go back to homepage",
        "output": "Step 1: Locate site logo or Home button. Step 2: Click logo or Home. Step 3: Verify homepage loads."
    },
    {
        "instruction": "browse product categories",
        "output": "Step 1: Locate navigation menu. Step 2: Hover over Categories. Step 3: Select category from dropdown. Step 4: Click subcategory if needed. Step 5: Verify category page loads."
    },
    
    # File Operations (UI only)
    {
        "instruction": "upload a profile picture",
        "output": "Step 1: Navigate to profile settings. Step 2: Click on profile picture area. Step 3: Click Upload Photo button. Step 4: Click Browse or Choose File. Step 5: Navigate to image location. Step 6: Select image file. Step 7: Click Open. Step 8: Click Save or Upload. Step 9: Verify image updates."
    },
    {
        "instruction": "download a file",
        "output": "Step 1: Navigate to file location. Step 2: Click download icon or button. Step 3: Verify download starts. Step 4: Check browser download bar. Step 5: Verify file downloaded completely."
    },
    {
        "instruction": "attach file to email",
        "output": "Step 1: Click Compose email. Step 2: Enter recipient. Step 3: Enter subject. Step 4: Click Attach button or paperclip icon. Step 5: Browse to file location. Step 6: Select file. Step 7: Click Open. Step 8: Verify file appears in attachments. Step 9: Click Send."
    },
    
    # Social Media
    {
        "instruction": "post a status update",
        "output": "Step 1: Navigate to social media homepage. Step 2: Locate status update box. Step 3: Click in text field. Step 4: Type status message. Step 5: Click Post or Share button. Step 6: Verify post appears in feed."
    },
    {
        "instruction": "like a post",
        "output": "Step 1: Locate post in feed. Step 2: Find like button or heart icon. Step 3: Click like button. Step 4: Verify icon changes to filled or colored."
    },
    {
        "instruction": "comment on a post",
        "output": "Step 1: Locate post. Step 2: Click Comment button. Step 3: Click in comment field. Step 4: Type comment text. Step 5: Click Post Comment. Step 6: Verify comment appears below post."
    },
    {
        "instruction": "share a post",
        "output": "Step 1: Locate post to share. Step 2: Click Share button. Step 3: Select share option. Step 4: Add comment if desired. Step 5: Click Share or Post. Step 6: Verify shared post appears."
    },
    {
        "instruction": "follow a user",
        "output": "Step 1: Navigate to user profile. Step 2: Locate Follow button. Step 3: Click Follow. Step 4: Verify button changes to Following."
    },
    
    # Email
    {
        "instruction": "send an email",
        "output": "Step 1: Click Compose or New Email. Step 2: Enter recipient email in To field. Step 3: Enter subject line. Step 4: Click in message body. Step 5: Type email message. Step 6: Click Send button. Step 7: Verify email sent confirmation."
    },
    {
        "instruction": "reply to an email",
        "output": "Step 1: Open email to reply to. Step 2: Click Reply button. Step 3: Type response message. Step 4: Click Send. Step 5: Verify email sent."
    },
    {
        "instruction": "forward an email",
        "output": "Step 1: Open email. Step 2: Click Forward button. Step 3: Enter recipient address. Step 4: Add message if needed. Step 5: Click Send. Step 6: Verify forwarded."
    },
    {
        "instruction": "delete an email",
        "output": "Step 1: Select email from list. Step 2: Click Delete or trash icon. Step 3: Verify email moves to trash. Step 4: Navigate to trash folder to confirm."
    },
    {
        "instruction": "mark email as unread",
        "output": "Step 1: Locate email in inbox. Step 2: Right-click email. Step 3: Select Mark as Unread. Step 4: Verify email appears bold."
    },
    
    # Calendar
    {
        "instruction": "create a calendar event",
        "output": "Step 1: Open calendar application. Step 2: Click Create or New Event. Step 3: Enter event title. Step 4: Select date. Step 5: Set start time. Step 6: Set end time. Step 7: Add location if needed. Step 8: Click Save. Step 9: Verify event appears on calendar."
    },
    {
        "instruction": "schedule a meeting",
        "output": "Step 1: Click New Meeting. Step 2: Enter meeting title. Step 3: Add participants' emails. Step 4: Select date and time. Step 5: Add meeting room or video link. Step 6: Set reminder. Step 7: Click Send Invites. Step 8: Verify invites sent."
    },
    {
        "instruction": "edit a calendar event",
        "output": "Step 1: Click on event. Step 2: Click Edit button. Step 3: Modify event details. Step 4: Click Save. Step 5: Verify changes appear."
    },
    
    # Search and Filter
    {
        "instruction": "search for specific text on page",
        "output": "Step 1: Press Ctrl+F. Step 2: Enter search term in find box. Step 3: Press Enter. Step 4: Verify text highlights on page. Step 5: Click next arrow to find other instances."
    },
    {
        "instruction": "filter table by column",
        "output": "Step 1: Locate filter icon in column header. Step 2: Click filter icon. Step 3: Enter filter value or select option. Step 4: Click Apply. Step 5: Verify table shows filtered rows only."
    },
    {
        "instruction": "apply multiple filters",
        "output": "Step 1: Click first filter dropdown. Step 2: Select filter option. Step 3: Click second filter dropdown. Step 4: Select another option. Step 5: Click Apply All. Step 6: Verify filtered results."
    },
    
    # Account Management
    {
        "instruction": "change profile picture",
        "output": "Step 1: Navigate to profile page. Step 2: Click Edit Profile. Step 3: Click on current picture. Step 4: Select Change Photo. Step 5: Upload new image. Step 6: Crop if needed. Step 7: Click Save. Step 8: Verify new picture appears."
    },
    {
        "instruction": "update email address",
        "output": "Step 1: Go to account settings. Step 2: Click Contact Information. Step 3: Click Edit next to email. Step 4: Enter new email address. Step 5: Enter password for verification. Step 6: Click Save. Step 7: Verify confirmation email sent. Step 8: Verify email in inbox."
    },
    {
        "instruction": "change password",
        "output": "Step 1: Navigate to security settings. Step 2: Click Change Password. Step 3: Enter current password. Step 4: Enter new password. Step 5: Confirm new password. Step 6: Click Update. Step 7: Verify success message."
    },
    {
        "instruction": "enable two-factor authentication",
        "output": "Step 1: Go to security settings. Step 2: Locate two-factor authentication section. Step 3: Click Enable or Turn On. Step 4: Select verification method. Step 5: Enter phone number or scan QR code. Step 6: Enter verification code. Step 7: Save backup codes. Step 8: Click Confirm. Step 9: Verify 2FA enabled status."
    },
    
    # Payment
    {
        "instruction": "add a payment method",
        "output": "Step 1: Navigate to payment settings. Step 2: Click Add Payment Method. Step 3: Select card type. Step 4: Enter card number. Step 5: Enter expiration date. Step 6: Enter CVV. Step 7: Enter billing address. Step 8: Click Save. Step 9: Verify card added."
    },
    {
        "instruction": "make a payment",
        "output": "Step 1: Navigate to payment page. Step 2: Enter amount. Step 3: Select payment method. Step 4: Review payment details. Step 5: Click Pay Now. Step 6: Enter CVV if prompted. Step 7: Click Confirm. Step 8: Verify payment success message."
    },
    
    # Notifications
    {
        "instruction": "enable email notifications",
        "output": "Step 1: Navigate to notification settings. Step 2: Locate email notifications section. Step 3: Toggle email notifications ON. Step 4: Select notification types. Step 5: Click Save Preferences. Step 6: Verify settings saved."
    },
    {
        "instruction": "mark all notifications as read",
        "output": "Step 1: Click notifications icon. Step 2: Locate Mark All as Read button. Step 3: Click button. Step 4: Verify all notifications marked."
    },
    
    # Reviews and Ratings
    {
        "instruction": "leave a product review",
        "output": "Step 1: Navigate to product page. Step 2: Scroll to reviews section. Step 3: Click Write Review. Step 4: Select star rating. Step 5: Enter review title. Step 6: Type review text. Step 7: Upload photos if option available. Step 8: Click Submit Review. Step 9: Verify review posted."
    },
    {
        "instruction": "rate a service",
        "output": "Step 1: Locate rating section. Step 2: Click on stars to rate. Step 3: Add written feedback if prompted. Step 4: Click Submit. Step 5: Verify rating submitted."
    },
    
    # Video/Media
    {
        "instruction": "play a video",
        "output": "Step 1: Navigate to video. Step 2: Click play button. Step 3: Verify video starts playing. Step 4: Adjust volume if needed."
    },
    {
        "instruction": "pause and resume video",
        "output": "Step 1: Click pause button during playback. Step 2: Verify video pauses. Step 3: Click play button. Step 4: Verify video resumes."
    },
    {
        "instruction": "adjust video quality",
        "output": "Step 1: Click settings icon on video player. Step 2: Select Quality option. Step 3: Choose resolution. Step 4: Verify quality changes."
    },
    
    # Messaging
    {
        "instruction": "send a message",
        "output": "Step 1: Open messaging app. Step 2: Click New Message. Step 3: Select or enter recipient. Step 4: Type message. Step 5: Click Send. Step 6: Verify message sent."
    },
    {
        "instruction": "start a group chat",
        "output": "Step 1: Click New Group. Step 2: Enter group name. Step 3: Add participants. Step 4: Click Create. Step 5: Send first message. Step 6: Verify group created."
    },
    
    # Shopping Cart
    {
        "instruction": "remove item from cart",
        "output": "Step 1: Click cart icon. Step 2: Locate item to remove. Step 3: Click Remove or X button. Step 4: Confirm removal if prompted. Step 5: Verify item removed from cart."
    },
    {
        "instruction": "update item quantity in cart",
        "output": "Step 1: Open shopping cart. Step 2: Locate quantity field for item. Step 3: Change quantity number. Step 4: Click Update or press Enter. Step 5: Verify total price updates."
    },
    {
        "instruction": "apply coupon code",
        "output": "Step 1: Navigate to cart. Step 2: Locate promo code field. Step 3: Enter coupon code. Step 4: Click Apply button. Step 5: Verify discount applied. Step 6: Check updated total."
    },
    
    # Browser Actions
    {
        "instruction": "bookmark current page",
        "output": "Step 1: Press Ctrl+D or click star icon. Step 2: Edit bookmark name if needed. Step 3: Select bookmark folder. Step 4: Click Save or Done. Step 5: Verify bookmark saved."
    },
    {
        "instruction": "open link in new tab",
        "output": "Step 1: Locate link. Step 2: Right-click on link. Step 3: Select Open in New Tab. Step 4: Verify new tab opens with page."
    },
    {
        "instruction": "refresh page",
        "output": "Step 1: Press F5 or click refresh button. Step 2: Verify page reloads. Step 3: Check for updated content."
    },
    {
        "instruction": "zoom in on page",
        "output": "Step 1: Press Ctrl and Plus key. Step 2: Verify page content enlarges. Step 3: Repeat if needed."
    },
    
    # Mobile App Actions
    {
        "instruction": "install mobile app",
        "output": "Step 1: Open app store. Step 2: Search for app name. Step 3: Tap app from results. Step 4: Tap Install button. Step 5: Authenticate if required. Step 6: Wait for installation. Step 7: Verify app appears on home screen."
    },
    {
        "instruction": "enable app notifications",
        "output": "Step 1: Open device settings. Step 2: Navigate to notifications. Step 3: Find app in list. Step 4: Tap app name. Step 5: Toggle Allow Notifications ON. Step 6: Select notification style. Step 7: Verify settings saved."
    },
    {
        "instruction": "swipe to delete item",
        "output": "Step 1: Locate item in list. Step 2: Swipe left on item. Step 3: Tap Delete button. Step 4: Confirm deletion if prompted. Step 5: Verify item removed."
    },
    
    # Verification Steps
    {
        "instruction": "verify page title",
        "output": "Step 1: Load the page. Step 2: Check browser tab title. Step 3: Verify title matches expected text."
    },
    {
        "instruction": "verify element is visible",
        "output": "Step 1: Navigate to page section. Step 2: Scroll to element if needed. Step 3: Verify element displays on screen."
    },
    {
        "instruction": "verify error message appears",
        "output": "Step 1: Perform invalid action. Step 2: Check for error message. Step 3: Verify error text is correct. Step 4: Verify error styling is red."
    },
    {
        "instruction": "verify button is disabled",
        "output": "Step 1: Locate button. Step 2: Check button appearance. Step 3: Attempt to click button. Step 4: Verify no action occurs."
    },
    
    # Dropdown and Select
    {
        "instruction": "select option from dropdown",
        "output": "Step 1: Locate dropdown menu. Step 2: Click dropdown. Step 3: Scroll to desired option if needed. Step 4: Click option. Step 5: Verify selection appears in dropdown."
    },
    {
        "instruction": "select multiple items from list",
        "output": "Step 1: Hold Ctrl key. Step 2: Click first item. Step 3: Click additional items while holding Ctrl. Step 4: Release Ctrl. Step 5: Verify all items selected."
    },
    
    # Checkbox and Radio
    {
        "instruction": "check a checkbox",
        "output": "Step 1: Locate checkbox. Step 2: Click checkbox. Step 3: Verify checkmark appears."
    },
    {
        "instruction": "select radio button",
        "output": "Step 1: Locate radio button group. Step 2: Click desired radio button. Step 3: Verify button is selected. Step 4: Verify other options deselected."
    },
    
    # Date/Time Pickers
    {
        "instruction": "select date from calendar picker",
        "output": "Step 1: Click date field. Step 2: Calendar popup opens. Step 3: Navigate to correct month if needed. Step 4: Click date. Step 5: Verify date appears in field."
    },
    {
        "instruction": "set time using time picker",
        "output": "Step 1: Click time field. Step 2: Select hour. Step 3: Select minute. Step 4: Select AM/PM if 12-hour format. Step 5: Click Done or OK. Step 6: Verify time in field."
    },
    
    # Tabs and Windows
    {
        "instruction": "switch between tabs",
        "output": "Step 1: Locate tab navigation. Step 2: Click desired tab. Step 3: Verify tab content displays. Step 4: Verify active tab highlighted."
    },
    {
        "instruction": "close current tab",
        "output": "Step 1: Locate close button on tab. Step 2: Click X button. Step 3: Verify tab closes. Step 4: Verify another tab becomes active."
    },
    
    # Modals and Popups
    {
        "instruction": "close popup modal",
        "output": "Step 1: Locate X or Close button. Step 2: Click button. Step 3: Verify modal closes. Step 4: Verify can interact with page again."
    },
    {
        "instruction": "accept cookie consent",
        "output": "Step 1: Locate cookie banner. Step 2: Click Accept or I Agree button. Step 3: Verify banner disappears."
    },
    
    # Scrolling
    {
        "instruction": "scroll to bottom of page",
        "output": "Step 1: Press End key or scroll down. Step 2: Continue scrolling until page bottom. Step 3: Verify at page end. Step 4: Check footer is visible."
    },
    {
        "instruction": "scroll to specific element",
        "output": "Step 1: Locate element position. Step 2: Scroll down or up. Step 3: Verify element in viewport. Step 4: Highlight element if needed."
    },
    
    # Print
    {
        "instruction": "print current page",
        "output": "Step 1: Press Ctrl+P. Step 2: Print dialog opens. Step 3: Select printer. Step 4: Choose page range. Step 5: Set number of copies. Step 6: Click Print. Step 7: Verify print job starts."
    },
    
    # Copy/Paste
    {
        "instruction": "copy text from page",
        "output": "Step 1: Highlight text to copy. Step 2: Press Ctrl+C. Step 3: Verify text copied to clipboard."
    },
    {
        "instruction": "paste text into field",
        "output": "Step 1: Click in target field. Step 2: Press Ctrl+V. Step 3: Verify text appears in field."
    }
]

print(f"Creating UI Test Automation dataset with {len(ui_automation_examples)} examples...")

# Write dataset
with open('automation_dataset.jsonl', 'w', encoding='utf-8') as f:
    for example in ui_automation_examples:
        f.write(json.dumps(example, ensure_ascii=False) + '\n')

print(f"✅ Created dataset with {len(ui_automation_examples)} UI automation examples")
print("\nDataset focuses on:")
print("- UI interactions only (Click, Enter, Navigate, Verify, Select)")
print("- No programming or implementation steps")
print("- Action verbs: Open, Click, Enter, Navigate, Verify, Select, etc.")
print("- Sequential test automation steps")
print("\nNext steps:")
print("1. Run: .\\venv\\Scripts\\python.exe scripts\\preprocess_automation.py")
print("2. Run: .\\venv\\Scripts\\python.exe run_training.py")
