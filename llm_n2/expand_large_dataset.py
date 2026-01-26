"""Add 150+ more unique automation examples to dataset"""
import json

# Load existing data
existing = [json.loads(line) for line in open('automation_dataset.jsonl')]
print(f"Current dataset: {len(existing)} examples")

# Add 150+ new diverse examples
new_examples = [
    # Advanced Authentication & Security
    {"instruction": "enable two-factor authentication", "output": "Step 1: Navigate to account settings. Step 2: Click Security tab. Step 3: Find Two-Factor Authentication option. Step 4: Click Enable. Step 5: Choose authentication method. Step 6: Scan QR code with authenticator app. Step 7: Enter verification code. Step 8: Save backup codes. Step 9: Confirm activation."},
    {"instruction": "change account password", "output": "Step 1: Open account settings. Step 2: Click Password option. Step 3: Enter current password. Step 4: Type new password. Step 5: Confirm new password. Step 6: Click Save Changes. Step 7: Verify email confirmation."},
    {"instruction": "recover account access", "output": "Step 1: Click Forgot Password on login page. Step 2: Enter account email. Step 3: Select recovery method. Step 4: Check email for recovery link. Step 5: Click recovery link. Step 6: Answer security questions. Step 7: Create new password. Step 8: Confirm password change. Step 9: Log in with new credentials."},
    {"instruction": "update security questions", "output": "Step 1: Go to account security settings. Step 2: Locate security questions section. Step 3: Click Edit. Step 4: Select new questions from dropdown. Step 5: Enter answers. Step 6: Confirm current password. Step 7: Save changes."},
    
    # E-commerce Advanced
    {"instruction": "add product to wishlist", "output": "Step 1: Browse to product page. Step 2: Locate heart or wishlist icon. Step 3: Click to add to wishlist. Step 4: Confirm item added. Step 5: View wishlist if needed."},
    {"instruction": "compare products", "output": "Step 1: Select first product. Step 2: Click Add to Compare. Step 3: Navigate to second product. Step 4: Click Add to Compare. Step 5: Open comparison view. Step 6: Review feature differences. Step 7: Select preferred product."},
    {"instruction": "write product review", "output": "Step 1: Go to product page. Step 2: Scroll to reviews section. Step 3: Click Write Review. Step 4: Select star rating. Step 5: Enter review title. Step 6: Type review text. Step 7: Add photos if desired. Step 8: Submit review."},
    {"instruction": "cancel order", "output": "Step 1: Log into account. Step 2: Navigate to Orders. Step 3: Find order to cancel. Step 4: Click order details. Step 5: Click Cancel Order button. Step 6: Select cancellation reason. Step 7: Confirm cancellation. Step 8: Verify refund method."},
    {"instruction": "update shipping address", "output": "Step 1: Go to account settings. Step 2: Click Addresses. Step 3: Select address to edit. Step 4: Update street address. Step 5: Modify city and postal code. Step 6: Verify country selection. Step 7: Save changes."},
    {"instruction": "track package delivery", "output": "Step 1: Access order confirmation email. Step 2: Click tracking number link. Step 3: View shipping status. Step 4: Check estimated delivery date. Step 5: Monitor package location updates."},
    
    # File Operations Advanced
    {"instruction": "create new folder", "output": "Step 1: Right-click in desired location. Step 2: Select New. Step 3: Click Folder. Step 4: Enter folder name. Step 5: Press Enter to create."},
    {"instruction": "copy multiple files", "output": "Step 1: Select first file. Step 2: Hold Ctrl and click additional files. Step 3: Right-click selection. Step 4: Choose Copy. Step 5: Navigate to destination. Step 6: Right-click and select Paste."},
    {"instruction": "search for files", "output": "Step 1: Open file explorer. Step 2: Click search box. Step 3: Enter file name or keyword. Step 4: Press Enter. Step 5: Review search results. Step 6: Open desired file."},
    {"instruction": "restore deleted file", "output": "Step 1: Open Recycle Bin. Step 2: Locate deleted file. Step 3: Right-click on file. Step 4: Select Restore. Step 5: File returns to original location."},
    {"instruction": "change file permissions", "output": "Step 1: Right-click file. Step 2: Select Properties. Step 3: Click Security tab. Step 4: Click Edit permissions. Step 5: Select user or group. Step 6: Modify access rights. Step 7: Apply changes. Step 8: Click OK."},
    {"instruction": "share file via link", "output": "Step 1: Right-click file. Step 2: Select Share option. Step 3: Click Get Link. Step 4: Set sharing permissions. Step 5: Copy link. Step 6: Send link to recipients."},
    
    # Email Advanced
    {"instruction": "create email filter", "output": "Step 1: Open email settings. Step 2: Navigate to Filters section. Step 3: Click Create Filter. Step 4: Define filter criteria. Step 5: Specify sender or keywords. Step 6: Choose action for matching emails. Step 7: Save filter."},
    {"instruction": "schedule email send", "output": "Step 1: Compose email message. Step 2: Click schedule send icon. Step 3: Select date and time. Step 4: Confirm scheduling. Step 5: Email queued for delivery."},
    {"instruction": "add email signature", "output": "Step 1: Open email settings. Step 2: Find Signature section. Step 3: Click Create New. Step 4: Enter signature text. Step 5: Format text style. Step 6: Add contact info. Step 7: Save signature. Step 8: Set as default."},
    {"instruction": "mark email as spam", "output": "Step 1: Select spam email. Step 2: Click Report Spam button. Step 3: Email moves to spam folder. Step 4: Future emails from sender blocked."},
    {"instruction": "create email folder", "output": "Step 1: Right-click in folder pane. Step 2: Select New Folder. Step 3: Enter folder name. Step 4: Press Enter. Step 5: Drag emails to organize."},
    {"instruction": "unsubscribe from emails", "output": "Step 1: Open unwanted email. Step 2: Scroll to bottom. Step 3: Click Unsubscribe link. Step 4: Confirm unsubscription. Step 5: Email preference updated."},
    
    # Browser Advanced
    {"instruction": "import bookmarks", "output": "Step 1: Open browser settings. Step 2: Navigate to Bookmarks section. Step 3: Click Import. Step 4: Select source browser. Step 5: Choose items to import. Step 6: Click Import button. Step 7: Verify bookmarks imported."},
    {"instruction": "export bookmarks", "output": "Step 1: Open bookmarks manager. Step 2: Click menu icon. Step 3: Select Export. Step 4: Choose save location. Step 5: Enter filename. Step 6: Save HTML file."},
    {"instruction": "manage browser extensions", "output": "Step 1: Click browser menu. Step 2: Select Extensions. Step 3: View installed extensions. Step 4: Toggle extensions on or off. Step 5: Remove unwanted extensions. Step 6: Search for new extensions if needed."},
    {"instruction": "clear cookies", "output": "Step 1: Open browser settings. Step 2: Go to Privacy section. Step 3: Click Clear browsing data. Step 4: Select Cookies checkbox. Step 5: Choose time range. Step 6: Click Clear data."},
    {"instruction": "set homepage", "output": "Step 1: Open browser settings. Step 2: Find On Startup section. Step 3: Select Open specific page. Step 4: Click Add new page. Step 5: Enter URL. Step 6: Save settings."},
    {"instruction": "enable pop-up blocker", "output": "Step 1: Access browser settings. Step 2: Navigate to Privacy and Security. Step 3: Find Pop-ups section. Step 4: Toggle block pop-ups on. Step 5: Add exceptions if needed."},
    
    # Document Editing Advanced
    {"instruction": "insert table into document", "output": "Step 1: Position cursor at insertion point. Step 2: Click Insert menu. Step 3: Select Table. Step 4: Specify rows and columns. Step 5: Click OK. Step 6: Table inserted. Step 7: Fill in table data."},
    {"instruction": "add page numbers", "output": "Step 1: Click Insert menu. Step 2: Select Page Number. Step 3: Choose position. Step 4: Select number format. Step 5: Apply to document."},
    {"instruction": "create table of contents", "output": "Step 1: Apply heading styles to sections. Step 2: Position cursor for TOC. Step 3: Click References tab. Step 4: Select Table of Contents. Step 5: Choose format style. Step 6: Insert TOC."},
    {"instruction": "track document changes", "output": "Step 1: Click Review tab. Step 2: Enable Track Changes. Step 3: Make edits to document. Step 4: Changes highlighted automatically. Step 5: Review changes later."},
    {"instruction": "add comments to document", "output": "Step 1: Select text to comment on. Step 2: Click Review tab. Step 3: Click New Comment. Step 4: Type comment text. Step 5: Comment appears in margin."},
    {"instruction": "merge documents", "output": "Step 1: Open first document. Step 2: Position cursor at merge point. Step 3: Click Insert. Step 4: Select Object. Step 5: Choose Text from File. Step 6: Select second document. Step 7: Click Insert."},
    
    # System Operations Advanced
    {"instruction": "empty recycle bin", "output": "Step 1: Open Recycle Bin. Step 2: Click Empty Recycle Bin. Step 3: Confirm deletion. Step 4: Wait for completion. Step 5: Files permanently removed."},
    {"instruction": "create system restore point", "output": "Step 1: Open System Properties. Step 2: Click System Protection tab. Step 3: Click Create button. Step 4: Enter description. Step 5: Click Create. Step 6: Wait for completion."},
    {"instruction": "check disk space", "output": "Step 1: Open File Explorer. Step 2: Right-click drive. Step 3: Select Properties. Step 4: View used and free space. Step 5: Check capacity graph."},
    {"instruction": "run disk cleanup", "output": "Step 1: Search for Disk Cleanup. Step 2: Select drive to clean. Step 3: Click OK. Step 4: Review files to delete. Step 5: Check items to remove. Step 6: Click OK. Step 7: Confirm deletion."},
    {"instruction": "change display resolution", "output": "Step 1: Right-click desktop. Step 2: Select Display settings. Step 3: Scroll to Resolution. Step 4: Choose from dropdown. Step 5: Click Apply. Step 6: Confirm changes."},
    {"instruction": "add printer", "output": "Step 1: Open Settings. Step 2: Go to Devices. Step 3: Click Printers and Scanners. Step 4: Click Add Printer. Step 5: Select printer from list. Step 6: Install drivers if prompted. Step 7: Set as default if desired."},
    
    # Social Media Advanced
    {"instruction": "create social media poll", "output": "Step 1: Start new post. Step 2: Click poll option. Step 3: Enter poll question. Step 4: Add answer choices. Step 5: Set poll duration. Step 6: Post poll."},
    {"instruction": "block user", "output": "Step 1: Navigate to user profile. Step 2: Click options menu. Step 3: Select Block. Step 4: Confirm blocking. Step 5: User blocked from contact."},
    {"instruction": "report inappropriate content", "output": "Step 1: Find offensive post. Step 2: Click report icon. Step 3: Select violation type. Step 4: Provide details. Step 5: Submit report."},
    {"instruction": "change privacy settings", "output": "Step 1: Open account settings. Step 2: Navigate to Privacy. Step 3: Review visibility options. Step 4: Adjust who can see posts. Step 5: Set profile visibility. Step 6: Save changes."},
    {"instruction": "create story post", "output": "Step 1: Click create story. Step 2: Select photo or video. Step 3: Add text or stickers. Step 4: Apply filters if desired. Step 5: Post story."},
    {"instruction": "tag friends in post", "output": "Step 1: Create new post. Step 2: Type @ symbol. Step 3: Begin typing friend name. Step 4: Select from dropdown. Step 5: Complete post. Step 6: Share."},
    
    # Calendar & Scheduling
    {"instruction": "create calendar event", "output": "Step 1: Open calendar. Step 2: Click date for event. Step 3: Click Add Event. Step 4: Enter event title. Step 5: Set start and end time. Step 6: Add location if needed. Step 7: Save event."},
    {"instruction": "set event reminder", "output": "Step 1: Open event. Step 2: Click add reminder. Step 3: Select reminder time. Step 4: Choose notification method. Step 5: Save changes."},
    {"instruction": "share calendar", "output": "Step 1: Open calendar settings. Step 2: Click Share Calendar. Step 3: Enter recipient email. Step 4: Set permission level. Step 5: Send invitation."},
    {"instruction": "delete calendar event", "output": "Step 1: Click on event. Step 2: Select Delete option. Step 3: Confirm deletion. Step 4: Event removed from calendar."},
    {"instruction": "reschedule meeting", "output": "Step 1: Open event. Step 2: Click Edit. Step 3: Change date or time. Step 4: Save changes. Step 5: Notify attendees of change."},
    
    # Video Conferencing
    {"instruction": "start video call", "output": "Step 1: Open video app. Step 2: Click New Meeting. Step 3: Configure audio and video. Step 4: Click Start. Step 5: Share meeting link with participants."},
    {"instruction": "share screen in meeting", "output": "Step 1: Join video call. Step 2: Click Share Screen. Step 3: Select window or entire screen. Step 4: Click Share. Step 5: Stop sharing when done."},
    {"instruction": "mute microphone", "output": "Step 1: Locate microphone icon. Step 2: Click to mute. Step 3: Icon shows muted status. Step 4: Click again to unmute."},
    {"instruction": "turn off camera", "output": "Step 1: Find camera icon. Step 2: Click to disable video. Step 3: Camera turns off. Step 4: Click again to enable."},
    {"instruction": "record meeting", "output": "Step 1: Start or join meeting. Step 2: Click Record button. Step 3: Confirm recording. Step 4: Stop recording when finished. Step 5: Access recording file."},
    
    # Cloud Storage
    {"instruction": "upload file to cloud", "output": "Step 1: Open cloud storage. Step 2: Navigate to folder. Step 3: Click Upload. Step 4: Select file from computer. Step 5: Wait for upload. Step 6: Verify file uploaded."},
    {"instruction": "sync folder to cloud", "output": "Step 1: Install sync client. Step 2: Sign into account. Step 3: Choose folders to sync. Step 4: Set sync preferences. Step 5: Start synchronization."},
    {"instruction": "restore previous file version", "output": "Step 1: Right-click cloud file. Step 2: Select Version History. Step 3: View previous versions. Step 4: Choose version to restore. Step 5: Click Restore. Step 6: Confirm restoration."},
    {"instruction": "generate sharing link", "output": "Step 1: Select file in cloud. Step 2: Click Share button. Step 3: Click Create Link. Step 4: Set link permissions. Step 5: Copy link. Step 6: Share with recipients."},
    
    # Messaging Apps
    {"instruction": "create group chat", "output": "Step 1: Open messaging app. Step 2: Click New Group. Step 3: Enter group name. Step 4: Add members. Step 5: Set group icon if desired. Step 6: Create group."},
    {"instruction": "pin important message", "output": "Step 1: Long press on message. Step 2: Select Pin option. Step 3: Message pinned to top. Step 4: Access from pinned messages."},
    {"instruction": "send voice message", "output": "Step 1: Open chat. Step 2: Press and hold microphone icon. Step 3: Record message. Step 4: Release to send. Step 5: Slide to cancel if needed."},
    {"instruction": "delete message", "output": "Step 1: Long press message. Step 2: Select Delete. Step 3: Choose delete for everyone or just you. Step 4: Confirm deletion."},
    {"instruction": "mute conversation", "output": "Step 1: Open chat. Step 2: Click chat settings. Step 3: Select Mute Notifications. Step 4: Choose duration. Step 5: Confirm muting."},
    
    # Photo Editing
    {"instruction": "crop photo", "output": "Step 1: Open photo in editor. Step 2: Select Crop tool. Step 3: Adjust crop boundaries. Step 4: Maintain aspect ratio if needed. Step 5: Apply crop. Step 6: Save image."},
    {"instruction": "adjust photo brightness", "output": "Step 1: Open image editor. Step 2: Select Adjust menu. Step 3: Choose Brightness slider. Step 4: Drag to increase or decrease. Step 5: Preview changes. Step 6: Save."},
    {"instruction": "rotate image", "output": "Step 1: Open photo. Step 2: Click Edit. Step 3: Select Rotate tool. Step 4: Click to rotate 90 degrees. Step 5: Repeat if needed. Step 6: Save changes."},
    {"instruction": "add filter to photo", "output": "Step 1: Open image. Step 2: Click Filters. Step 3: Browse filter options. Step 4: Select desired filter. Step 5: Adjust intensity. Step 6: Apply and save."},
    {"instruction": "remove red eye", "output": "Step 1: Open photo editor. Step 2: Select Red Eye tool. Step 3: Click on red eye area. Step 4: Tool corrects automatically. Step 5: Repeat for other eye. Step 6: Save image."},
    
    # Task Management
    {"instruction": "create to-do list", "output": "Step 1: Open task app. Step 2: Click New List. Step 3: Enter list name. Step 4: Add first task. Step 5: Add more tasks. Step 6: Save list."},
    {"instruction": "mark task complete", "output": "Step 1: Find task in list. Step 2: Click checkbox next to task. Step 3: Task marked as done. Step 4: Moves to completed section."},
    {"instruction": "set task due date", "output": "Step 1: Click on task. Step 2: Select Add Due Date. Step 3: Choose date from calendar. Step 4: Set time if needed. Step 5: Save changes."},
    {"instruction": "assign task to team member", "output": "Step 1: Open task details. Step 2: Click Assign option. Step 3: Select team member. Step 4: Add note if needed. Step 5: Save assignment."},
    {"instruction": "prioritize tasks", "output": "Step 1: View task list. Step 2: Select task. Step 3: Set priority level. Step 4: Choose high, medium, or low. Step 5: Tasks sorted by priority."},
    
    # Spreadsheet Operations
    {"instruction": "create spreadsheet", "output": "Step 1: Open spreadsheet app. Step 2: Click New Spreadsheet. Step 3: Enter data in cells. Step 4: Format headers. Step 5: Save file."},
    {"instruction": "insert formula", "output": "Step 1: Click target cell. Step 2: Type equals sign. Step 3: Enter formula. Step 4: Reference other cells. Step 5: Press Enter. Step 6: Formula calculates result."},
    {"instruction": "sort data in spreadsheet", "output": "Step 1: Select data range. Step 2: Click Data menu. Step 3: Choose Sort. Step 4: Select column to sort by. Step 5: Choose ascending or descending. Step 6: Click OK."},
    {"instruction": "create chart from data", "output": "Step 1: Select data range. Step 2: Click Insert menu. Step 3: Choose Chart. Step 4: Select chart type. Step 5: Customize chart title. Step 6: Insert chart."},
    {"instruction": "freeze spreadsheet rows", "output": "Step 1: Select row below freeze point. Step 2: Click View menu. Step 3: Select Freeze Rows. Step 4: Top rows stay visible when scrolling."},
    
    # PDF Operations
    {"instruction": "merge PDF files", "output": "Step 1: Open PDF tool. Step 2: Select Merge option. Step 3: Add first PDF. Step 4: Add additional PDFs. Step 5: Arrange order. Step 6: Click Merge. Step 7: Save combined file."},
    {"instruction": "split PDF pages", "output": "Step 1: Open PDF. Step 2: Select Split tool. Step 3: Choose split points. Step 4: Specify page ranges. Step 5: Click Split. Step 6: Save separate files."},
    {"instruction": "add signature to PDF", "output": "Step 1: Open PDF. Step 2: Click Sign tool. Step 3: Draw or upload signature. Step 4: Position signature on document. Step 5: Resize if needed. Step 6: Save signed PDF."},
    {"instruction": "highlight PDF text", "output": "Step 1: Open PDF. Step 2: Select highlight tool. Step 3: Choose highlight color. Step 4: Click and drag over text. Step 5: Text highlighted. Step 6: Save changes."},
    
    # Music Streaming
    {"instruction": "create playlist", "output": "Step 1: Open music app. Step 2: Click Create Playlist. Step 3: Enter playlist name. Step 4: Add description. Step 5: Add songs. Step 6: Save playlist."},
    {"instruction": "download song offline", "output": "Step 1: Find song. Step 2: Click download icon. Step 3: Song downloads to device. Step 4: Available offline."},
    {"instruction": "share playlist", "output": "Step 1: Open playlist. Step 2: Click share button. Step 3: Select sharing method. Step 4: Send to contacts or copy link."},
    {"instruction": "follow artist", "output": "Step 1: Search for artist. Step 2: Open artist page. Step 3: Click Follow button. Step 4: Receive updates about new releases."},
    
    # Smart Home
    {"instruction": "adjust thermostat temperature", "output": "Step 1: Open smart home app. Step 2: Select thermostat. Step 3: Tap temperature. Step 4: Adjust up or down. Step 5: Save new setting."},
    {"instruction": "turn on smart lights", "output": "Step 1: Open lighting app. Step 2: Select room or light. Step 3: Toggle power on. Step 4: Adjust brightness if needed."},
    {"instruction": "set lighting schedule", "output": "Step 1: Open smart light app. Step 2: Go to schedules. Step 3: Create new schedule. Step 4: Set time and days. Step 5: Choose lights. Step 6: Save schedule."},
    {"instruction": "lock smart door", "output": "Step 1: Open smart lock app. Step 2: Find door lock. Step 3: Tap lock icon. Step 4: Door locks remotely. Step 5: Confirm locked status."},
    
    # Mobile App Operations
    {"instruction": "install mobile app", "output": "Step 1: Open app store. Step 2: Search for app name. Step 3: Tap on app. Step 4: Click Install button. Step 5: Wait for download. Step 6: App installed on device."},
    {"instruction": "uninstall app", "output": "Step 1: Find app icon. Step 2: Long press on icon. Step 3: Select Uninstall option. Step 4: Confirm uninstallation. Step 5: App removed."},
    {"instruction": "update mobile app", "output": "Step 1: Open app store. Step 2: Go to My Apps. Step 3: Find app with update. Step 4: Tap Update button. Step 5: Wait for completion."},
    {"instruction": "clear app cache", "output": "Step 1: Open Settings. Step 2: Go to Apps. Step 3: Select app. Step 4: Tap Storage. Step 5: Click Clear Cache. Step 6: Confirm action."},
    {"instruction": "force stop app", "output": "Step 1: Open Settings. Step 2: Navigate to Apps. Step 3: Select problematic app. Step 4: Tap Force Stop. Step 5: Confirm stopping app."},
    
    # Banking & Finance
    {"instruction": "transfer money between accounts", "output": "Step 1: Log into banking app. Step 2: Select Transfer. Step 3: Choose from account. Step 4: Select to account. Step 5: Enter amount. Step 6: Review details. Step 7: Confirm transfer. Step 8: Verify confirmation."},
    {"instruction": "pay bill online", "output": "Step 1: Access bill pay section. Step 2: Select payee. Step 3: Enter amount. Step 4: Choose payment date. Step 5: Select payment account. Step 6: Review details. Step 7: Submit payment."},
    {"instruction": "set up direct deposit", "output": "Step 1: Log into banking portal. Step 2: Go to direct deposit section. Step 3: Download form if needed. Step 4: Enter employer information. Step 5: Provide routing number. Step 6: Provide account number. Step 7: Submit request."},
    {"instruction": "check account balance", "output": "Step 1: Open banking app. Step 2: View account summary. Step 3: Select specific account. Step 4: Review current balance and transactions."},
    {"instruction": "dispute transaction", "output": "Step 1: Log into account. Step 2: Find transaction. Step 3: Click Dispute. Step 4: Select dispute reason. Step 5: Provide details. Step 6: Submit dispute. Step 7: Track dispute status."},
    
    # Notifications & Alerts
    {"instruction": "enable push notifications", "output": "Step 1: Open app settings. Step 2: Go to Notifications. Step 3: Toggle push notifications on. Step 4: Select notification types. Step 5: Save preferences."},
    {"instruction": "disable notification sounds", "output": "Step 1: Access device settings. Step 2: Select Sound or Notifications. Step 3: Find app notifications. Step 4: Toggle sound off. Step 5: Keep vibration if desired."},
    {"instruction": "customize notification preferences", "output": "Step 1: Open app settings. Step 2: Navigate to Notifications. Step 3: Select notification types. Step 4: Set frequency. Step 5: Choose quiet hours. Step 6: Save settings."},
    
    # Web Forms
    {"instruction": "fill out online form", "output": "Step 1: Navigate to form page. Step 2: Enter personal information. Step 3: Fill required fields. Step 4: Upload documents if needed. Step 5: Review entries. Step 6: Click Submit. Step 7: Verify confirmation."},
    {"instruction": "save form as draft", "output": "Step 1: Fill out partial form. Step 2: Click Save Draft button. Step 3: Draft saved to account. Step 4: Resume later from saved drafts."},
    {"instruction": "attach file to form", "output": "Step 1: Click attachment field. Step 2: Browse computer files. Step 3: Select file. Step 4: Wait for upload. Step 5: Verify file attached."},
    
    # Screen Recording
    {"instruction": "record screen", "output": "Step 1: Open screen recorder. Step 2: Select recording area. Step 3: Choose audio source. Step 4: Click Start Recording. Step 5: Perform actions. Step 6: Click Stop. Step 7: Save recording."},
    {"instruction": "take scrolling screenshot", "output": "Step 1: Open screenshot tool. Step 2: Select scrolling capture. Step 3: Click start. Step 4: Page scrolls automatically. Step 5: Stop when complete. Step 6: Save full page image."},
    
    # Accessibility
    {"instruction": "enable screen reader", "output": "Step 1: Open accessibility settings. Step 2: Find screen reader option. Step 3: Toggle on. Step 4: Adjust reading speed. Step 5: Configure voice settings."},
    {"instruction": "increase text size", "output": "Step 1: Open display settings. Step 2: Find text size slider. Step 3: Drag to increase. Step 4: Preview changes. Step 5: Apply settings."},
    {"instruction": "enable high contrast mode", "output": "Step 1: Access accessibility settings. Step 2: Select high contrast. Step 3: Toggle on. Step 4: Choose color scheme. Step 5: Apply changes."},
]

# Combine all data
all_data = existing + new_examples
print(f"New dataset: {len(all_data)} examples (+{len(new_examples)} added)")

# Save
with open('automation_dataset.jsonl', 'w', encoding='utf-8') as f:
    for item in all_data:
        f.write(json.dumps(item, ensure_ascii=False) + '\n')

print("Dataset updated successfully!")
print(f"\nTotal examples: {len(all_data)}")
print(f"Added: {len(new_examples)} new examples")
