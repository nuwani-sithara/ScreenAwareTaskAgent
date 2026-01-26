"""Expand automation dataset with more examples"""
import json

# Load existing data
existing = [json.loads(line) for line in open('automation_dataset.jsonl')]
print(f"Current dataset: {len(existing)} examples")

# Add many more varied examples
new_examples = [
    # Web Authentication
    {"instruction": "sign in to account", "output": "Step 1: Navigate to sign in page. Step 2: Locate email or username field. Step 3: Enter credentials. Step 4: Locate password field. Step 5: Enter password. Step 6: Click sign in button. Step 7: Wait for authentication."},
    {"instruction": "log out from system", "output": "Step 1: Locate user menu or profile icon. Step 2: Click to expand menu. Step 3: Find log out option. Step 4: Click log out. Step 5: Confirm logout if prompted. Step 6: Wait for redirect to login page."},
    {"instruction": "reset forgotten password", "output": "Step 1: Navigate to login page. Step 2: Click Forgot Password link. Step 3: Enter email address. Step 4: Click Submit. Step 5: Check email for reset link. Step 6: Click link in email. Step 7: Enter new password. Step 8: Confirm new password. Step 9: Submit password change."},
    {"instruction": "verify email address", "output": "Step 1: Check email inbox. Step 2: Find verification email. Step 3: Open verification email. Step 4: Click verification link. Step 5: Wait for confirmation page to load. Step 6: Verify success message displayed."},
    
    # E-commerce
    {"instruction": "purchase product online", "output": "Step 1: Search for product. Step 2: Select desired product. Step 3: Choose size or options. Step 4: Click Add to Cart. Step 5: Navigate to cart. Step 6: Click Proceed to Checkout. Step 7: Enter shipping address. Step 8: Select payment method. Step 9: Enter payment details. Step 10: Review order. Step 11: Click Place Order."},
    {"instruction": "apply discount code", "output": "Step 1: Navigate to shopping cart. Step 2: Locate promo code field. Step 3: Enter discount code. Step 4: Click Apply button. Step 5: Verify discount is applied. Step 6: Check updated total price."},
    {"instruction": "track order status", "output": "Step 1: Log in to account. Step 2: Navigate to My Orders. Step 3: Find specific order. Step 4: Click View Details. Step 5: Check tracking information. Step 6: View estimated delivery date."},
    {"instruction": "return purchased item", "output": "Step 1: Go to Order History. Step 2: Select order to return. Step 3: Click Return Item button. Step 4: Select reason for return. Step 5: Choose refund method. Step 6: Print return label. Step 7: Package item. Step 8: Ship to return address."},
    
    # File Management
    {"instruction": "rename file", "output": "Step 1: Locate file in file explorer. Step 2: Right-click on file. Step 3: Select Rename from menu. Step 4: Clear current name. Step 5: Type new name. Step 6: Press Enter to confirm."},
    {"instruction": "move file to folder", "output": "Step 1: Select file. Step 2: Right-click and choose Cut or press Ctrl+X. Step 3: Navigate to destination folder. Step 4: Right-click in folder. Step 5: Select Paste or press Ctrl+V. Step 6: Verify file moved successfully."},
    {"instruction": "compress files to zip", "output": "Step 1: Select files to compress. Step 2: Right-click on selection. Step 3: Choose Send to option. Step 4: Select Compressed folder. Step 5: Enter zip file name. Step 6: Press Enter. Step 7: Wait for compression to complete."},
    {"instruction": "extract zip archive", "output": "Step 1: Locate zip file. Step 2: Right-click on zip file. Step 3: Select Extract All. Step 4: Choose extraction location. Step 5: Click Extract button. Step 6: Wait for extraction. Step 7: Open extracted folder."},
    
    # Email Operations
    {"instruction": "compose new email", "output": "Step 1: Open email application. Step 2: Click Compose or New Email button. Step 3: Enter recipient email address. Step 4: Fill in subject line. Step 5: Type email message. Step 6: Add attachments if needed. Step 7: Review email. Step 8: Click Send button."},
    {"instruction": "reply to email", "output": "Step 1: Open email to reply to. Step 2: Click Reply button. Step 3: Type your response. Step 4: Add any additional recipients if needed. Step 5: Review message. Step 6: Click Send."},
    {"instruction": "forward email", "output": "Step 1: Open email to forward. Step 2: Click Forward button. Step 3: Enter recipient email address. Step 4: Add forwarding message if needed. Step 5: Click Send."},
    {"instruction": "delete spam email", "output": "Step 1: Select spam email. Step 2: Click Delete or trash icon. Step 3: Confirm deletion if prompted. Step 4: Email moves to trash folder."},
    
    # Browser Operations
    {"instruction": "bookmark current page", "output": "Step 1: Press Ctrl+D or click star icon. Step 2: Edit bookmark name if needed. Step 3: Choose bookmark folder. Step 4: Click Save or Done."},
    {"instruction": "clear browsing history", "output": "Step 1: Open browser settings. Step 2: Navigate to Privacy section. Step 3: Click Clear browsing data. Step 4: Select time range. Step 5: Choose data types to clear. Step 6: Click Clear data button. Step 7: Wait for completion."},
    {"instruction": "open incognito window", "output": "Step 1: Click browser menu. Step 2: Select New Incognito Window or press Ctrl+Shift+N. Step 3: New private window opens."},
    {"instruction": "zoom in on webpage", "output": "Step 1: Press Ctrl and + key together. Step 2: Or use browser zoom controls. Step 3: Repeat to zoom further."},
    
    # Document Editing  
    {"instruction": "create new document", "output": "Step 1: Open document application. Step 2: Click File menu. Step 3: Select New Document. Step 4: Choose document type. Step 5: New blank document opens."},
    {"instruction": "save document as PDF", "output": "Step 1: Click File menu. Step 2: Select Save As or Export. Step 3: Choose PDF format from dropdown. Step 4: Enter file name. Step 5: Select save location. Step 6: Click Save button."},
    {"instruction": "insert image into document", "output": "Step 1: Place cursor at insertion point. Step 2: Click Insert menu. Step 3: Select Image or Picture. Step 4: Browse for image file. Step 5: Select image. Step 6: Click Insert. Step 7: Resize if needed."},
    {"instruction": "find and replace text", "output": "Step 1: Press Ctrl+H or open Edit menu. Step 2: Select Find and Replace. Step 3: Enter text to find. Step 4: Enter replacement text. Step 5: Click Replace All or Replace individually. Step 6: Close dialog."},
    
    # System Operations
    {"instruction": "take screenshot", "output": "Step 1: Press Windows+PrintScreen or use Snipping Tool. Step 2: Select screenshot area. Step 3: Screenshot is captured. Step 4: Screenshot saves to Pictures folder."},
    {"instruction": "connect to wifi network", "output": "Step 1: Click network icon in taskbar. Step 2: View available networks. Step 3: Select desired network. Step 4: Click Connect. Step 5: Enter password if required. Step 6: Click Next. Step 7: Wait for connection."},
    {"instruction": "adjust screen brightness", "output": "Step 1: Click battery or settings icon. Step 2: Locate brightness slider. Step 3: Drag slider to adjust. Step 4: Or use keyboard brightness keys. Step 5: Changes apply immediately."},
    {"instruction": "check system updates", "output": "Step 1: Open Settings. Step 2: Navigate to Update & Security. Step 3: Click Check for updates. Step 4: Wait for update scan. Step 5: View available updates. Step 6: Click Install if updates found."},
    
    # Social Media
    {"instruction": "post status update", "output": "Step 1: Open social media app. Step 2: Click compose or post button. Step 3: Type status message. Step 4: Add media if desired. Step 5: Set privacy settings. Step 6: Click Post or Share button."},
    {"instruction": "like a post", "output": "Step 1: Locate post to like. Step 2: Click like button or icon. Step 3: Like is registered. Step 4: Icon changes to show liked status."},
    {"instruction": "comment on post", "output": "Step 1: Find post to comment on. Step 2: Click comment icon or box. Step 3: Type comment message. Step 4: Click Post Comment button. Step 5: Comment appears below post."},
    {"instruction": "share post with friends", "output": "Step 1: Click share icon on post. Step 2: Select sharing method. Step 3: Choose recipients. Step 4: Add optional message. Step 5: Click Share button."},
]

# Combine
all_data = existing + new_examples
print(f"New dataset: {len(all_data)} examples (+{len(new_examples)} added)")

# Save
with open('automation_dataset_expanded.jsonl', 'w') as f:
    for item in all_data:
        f.write(json.dumps(item) + '\n')

print("Saved to: automation_dataset_expanded.jsonl")
print("\nNext steps:")
print("1. Replace automation_dataset.jsonl with expanded version")
print("2. Run: .\\venv\\Scripts\\python.exe scripts\\preprocess_automation.py")
print("3. Run: .\\venv\\Scripts\\python.exe scripts\\train_automation.py")
