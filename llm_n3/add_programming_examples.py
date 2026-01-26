"""Add programming and development examples to automation dataset"""
import json

# Programming and development examples
programming_examples = [
    # JavaScript/Web Development
    {
        "instruction": "create a JS app to add 2 numbers",
        "output": "Step 1: Open text editor or IDE. Step 2: Create new HTML file. Step 3: Add HTML structure with input fields. Step 4: Create script tag. Step 5: Write JavaScript function to get input values. Step 6: Add numbers and display result. Step 7: Add button to trigger calculation. Step 8: Save and test in browser."
    },
    {
        "instruction": "create a JavaScript calculator",
        "output": "Step 1: Create HTML file with calculator UI. Step 2: Add input display and number buttons. Step 3: Add operator buttons. Step 4: Write JavaScript functions for operations. Step 5: Implement event listeners. Step 6: Add clear and equals functionality. Step 7: Test all operations."
    },
    {
        "instruction": "build a simple web form",
        "output": "Step 1: Create HTML file. Step 2: Add form element with input fields. Step 3: Add labels for each field. Step 4: Include submit button. Step 5: Write JavaScript validation. Step 6: Add event listener for form submission. Step 7: Display submitted data or errors."
    },
    {
        "instruction": "create a to-do list app in JavaScript",
        "output": "Step 1: Create HTML with input and list container. Step 2: Add CSS for styling. Step 3: Write JavaScript to add new items. Step 4: Implement delete functionality. Step 5: Add mark as complete feature. Step 6: Store data in localStorage. Step 7: Load saved items on page load."
    },
    {
        "instruction": "make a countdown timer in JavaScript",
        "output": "Step 1: Create HTML with display area. Step 2: Add input for time duration. Step 3: Write JavaScript countdown function. Step 4: Use setInterval for updates. Step 5: Add start and stop buttons. Step 6: Display remaining time. Step 7: Alert when timer completes."
    },
    
    # Python Programming
    {
        "instruction": "write a Python script to add two numbers",
        "output": "Step 1: Open text editor or IDE. Step 2: Create new Python file. Step 3: Get first number from user input. Step 4: Get second number from user input. Step 5: Convert inputs to integers or floats. Step 6: Add the numbers. Step 7: Print the result. Step 8: Save and run script."
    },
    {
        "instruction": "create a Python calculator program",
        "output": "Step 1: Import necessary modules. Step 2: Define functions for add, subtract, multiply, divide. Step 3: Create menu to display operations. Step 4: Get user choice. Step 5: Get numbers from user. Step 6: Call appropriate function. Step 7: Display result. Step 8: Add loop for continuous operation."
    },
    {
        "instruction": "write Python code to read a file",
        "output": "Step 1: Open Python editor. Step 2: Use open function with file path. Step 3: Specify read mode. Step 4: Read file content using read or readlines. Step 5: Process content as needed. Step 6: Close file or use with statement. Step 7: Handle file not found errors."
    },
    {
        "instruction": "create a Python program to sort a list",
        "output": "Step 1: Create or input list of numbers. Step 2: Use built-in sort method or sorted function. Step 3: Optionally specify reverse order. Step 4: Print sorted list. Step 5: Test with different inputs."
    },
    {
        "instruction": "build a simple Python web scraper",
        "output": "Step 1: Install requests and BeautifulSoup libraries. Step 2: Import modules. Step 3: Send HTTP request to URL. Step 4: Parse HTML content. Step 5: Find target elements using selectors. Step 6: Extract desired data. Step 7: Save or display results."
    },
    
    # General Programming
    {
        "instruction": "create a simple console application",
        "output": "Step 1: Choose programming language. Step 2: Open IDE or editor. Step 3: Create new project or file. Step 4: Write main function or entry point. Step 5: Add user input prompts. Step 6: Implement core logic. Step 7: Display output to console. Step 8: Test and debug."
    },
    {
        "instruction": "write code to connect to a database",
        "output": "Step 1: Import database library. Step 2: Define connection parameters. Step 3: Establish database connection. Step 4: Create cursor object. Step 5: Execute SQL query. Step 6: Fetch results if needed. Step 7: Close cursor and connection. Step 8: Handle exceptions."
    },
    {
        "instruction": "create a REST API endpoint",
        "output": "Step 1: Set up web framework. Step 2: Create route handler. Step 3: Define HTTP method. Step 4: Add request parameter validation. Step 5: Implement business logic. Step 6: Format response data. Step 7: Return JSON response with status code. Step 8: Test endpoint."
    },
    {
        "instruction": "implement user authentication in app",
        "output": "Step 1: Create user model with credentials. Step 2: Hash passwords before storage. Step 3: Create login endpoint. Step 4: Verify credentials. Step 5: Generate authentication token. Step 6: Return token to client. Step 7: Protect routes with middleware. Step 8: Handle token validation."
    },
    {
        "instruction": "write unit tests for a function",
        "output": "Step 1: Import testing framework. Step 2: Create test class or file. Step 3: Write test function for each scenario. Step 4: Set up test data. Step 5: Call function with test inputs. Step 6: Assert expected outputs. Step 7: Test edge cases. Step 8: Run all tests."
    },
    
    # HTML/CSS
    {
        "instruction": "create a responsive navigation menu",
        "output": "Step 1: Write HTML structure with nav element. Step 2: Add list items for menu links. Step 3: Style with CSS for desktop view. Step 4: Add media query for mobile. Step 5: Create hamburger icon. Step 6: Write JavaScript for toggle. Step 7: Test on different screen sizes."
    },
    {
        "instruction": "build a landing page layout",
        "output": "Step 1: Create HTML structure. Step 2: Add header with logo and nav. Step 3: Create hero section with headline. Step 4: Add features section. Step 5: Style with CSS Grid or Flexbox. Step 6: Make responsive with media queries. Step 7: Add images and colors. Step 8: Test on devices."
    },
    {
        "instruction": "design a contact form with validation",
        "output": "Step 1: Create HTML form with fields. Step 2: Add required attributes. Step 3: Style form with CSS. Step 4: Write JavaScript validation. Step 5: Check for empty fields. Step 6: Validate email format. Step 7: Display error messages. Step 8: Submit if valid."
    },
    
    # Development Tools
    {
        "instruction": "initialize a Git repository",
        "output": "Step 1: Open terminal in project folder. Step 2: Run git init command. Step 3: Create gitignore file. Step 4: Add files with git add. Step 5: Make initial commit. Step 6: Optionally add remote repository. Step 7: Push to remote if configured."
    },
    {
        "instruction": "create a new branch in Git",
        "output": "Step 1: Open terminal in repository. Step 2: Check current branch with git branch. Step 3: Run git checkout -b branch-name. Step 4: Make changes in new branch. Step 5: Commit changes. Step 6: Push branch to remote. Step 7: Create pull request if needed."
    },
    {
        "instruction": "install NPM packages for project",
        "output": "Step 1: Navigate to project directory. Step 2: Ensure package.json exists. Step 3: Run npm install package-name. Step 4: Verify package added to dependencies. Step 5: Import package in code. Step 6: Use package functionality. Step 7: Commit package.json changes."
    },
    {
        "instruction": "set up a Node.js project",
        "output": "Step 1: Create project folder. Step 2: Open terminal in folder. Step 3: Run npm init. Step 4: Answer setup questions. Step 5: Install required packages. Step 6: Create index.js file. Step 7: Add start script to package.json. Step 8: Test with npm start."
    },
    {
        "instruction": "deploy application to server",
        "output": "Step 1: Build production version. Step 2: Connect to server via SSH or FTP. Step 3: Upload build files. Step 4: Install dependencies on server. Step 5: Configure environment variables. Step 6: Start application service. Step 7: Verify app is running. Step 8: Test live URL."
    },
    
    # Database
    {
        "instruction": "create a new database table",
        "output": "Step 1: Connect to database. Step 2: Write CREATE TABLE SQL statement. Step 3: Define column names and types. Step 4: Add primary key constraint. Step 5: Add other constraints if needed. Step 6: Execute SQL statement. Step 7: Verify table created. Step 8: Add initial data if needed."
    },
    {
        "instruction": "perform SQL query to fetch data",
        "output": "Step 1: Open database client. Step 2: Write SELECT statement. Step 3: Specify columns to retrieve. Step 4: Add FROM clause with table name. Step 5: Add WHERE conditions if needed. Step 6: Add ORDER BY if needed. Step 7: Execute query. Step 8: Review results."
    },
    {
        "instruction": "update records in database",
        "output": "Step 1: Write UPDATE SQL statement. Step 2: Specify table name. Step 3: Set new values with SET clause. Step 4: Add WHERE clause to target records. Step 5: Review query carefully. Step 6: Execute update. Step 7: Verify affected rows count. Step 8: Confirm changes."
    },
    
    # Mobile/App Development
    {
        "instruction": "create a mobile app screen layout",
        "output": "Step 1: Open mobile development IDE. Step 2: Create new screen or activity. Step 3: Add layout container. Step 4: Place UI components. Step 5: Set component properties. Step 6: Add styling and colors. Step 7: Preview on emulator. Step 8: Test on device."
    },
    {
        "instruction": "implement button click handler",
        "output": "Step 1: Locate button in layout. Step 2: Add button ID. Step 3: Find button in code. Step 4: Create click listener function. Step 5: Attach listener to button. Step 6: Implement action logic. Step 7: Test button click. Step 8: Handle edge cases."
    },
    
    # Code Quality
    {
        "instruction": "refactor code for better readability",
        "output": "Step 1: Identify complex functions. Step 2: Break into smaller functions. Step 3: Use descriptive variable names. Step 4: Remove duplicate code. Step 5: Add comments for clarity. Step 6: Follow naming conventions. Step 7: Run tests to ensure functionality. Step 8: Review changes."
    },
    {
        "instruction": "debug a runtime error",
        "output": "Step 1: Read error message carefully. Step 2: Identify error location and line. Step 3: Add breakpoint or console logs. Step 4: Run code in debug mode. Step 5: Inspect variable values. Step 6: Trace execution flow. Step 7: Identify root cause. Step 8: Fix and test."
    },
    {
        "instruction": "optimize slow running code",
        "output": "Step 1: Profile code to find bottlenecks. Step 2: Identify slow operations. Step 3: Review algorithm complexity. Step 4: Use efficient data structures. Step 5: Reduce unnecessary loops. Step 6: Cache repeated calculations. Step 7: Test performance improvements. Step 8: Verify correctness maintained."
    },
    
    # React/Frontend Frameworks
    {
        "instruction": "create a React component",
        "output": "Step 1: Create new component file. Step 2: Import React. Step 3: Define function component. Step 4: Add props parameters. Step 5: Write JSX return statement. Step 6: Add state with useState if needed. Step 7: Export component. Step 8: Import and use in app."
    },
    {
        "instruction": "add state management to React app",
        "output": "Step 1: Import useState or useReducer. Step 2: Declare state variable. Step 3: Initialize state value. Step 4: Create update functions. Step 5: Use state in component. Step 6: Trigger updates on events. Step 7: Pass state to child components. Step 8: Test state changes."
    },
    {
        "instruction": "fetch data from API in React",
        "output": "Step 1: Import useEffect and useState. Step 2: Create state for data. Step 3: Define fetch function. Step 4: Call API with fetch or axios. Step 5: Parse JSON response. Step 6: Update state with data. Step 7: Use useEffect to call on mount. Step 8: Handle loading and errors."
    },
    
    # Additional Programming Tasks
    {
        "instruction": "write a loop to iterate through array",
        "output": "Step 1: Declare or obtain array. Step 2: Choose loop type. Step 3: Write for or forEach loop. Step 4: Access current element. Step 5: Perform operation on element. Step 6: Use index if needed. Step 7: Continue until array end. Step 8: Test with sample data."
    },
    {
        "instruction": "create a class with methods",
        "output": "Step 1: Define class with class keyword. Step 2: Add constructor method. Step 3: Initialize properties. Step 4: Create instance methods. Step 5: Add parameters to methods. Step 6: Implement method logic. Step 7: Create class instance. Step 8: Call methods and test."
    },
    {
        "instruction": "handle errors with try-catch",
        "output": "Step 1: Wrap risky code in try block. Step 2: Add catch block. Step 3: Catch error parameter. Step 4: Log or handle error. Step 5: Optionally add finally block. Step 6: Clean up resources. Step 7: Test error scenarios. Step 8: Ensure app doesn't crash."
    },
    {
        "instruction": "convert JSON to object",
        "output": "Step 1: Obtain JSON string. Step 2: Use JSON.parse method. Step 3: Pass JSON string as argument. Step 4: Store result in variable. Step 5: Access object properties. Step 6: Handle parse errors with try-catch. Step 7: Validate data structure. Step 8: Use parsed object."
    },
    {
        "instruction": "create a function with parameters",
        "output": "Step 1: Use function keyword or arrow syntax. Step 2: Name the function. Step 3: Add parameters in parentheses. Step 4: Open function body with braces. Step 5: Write function logic. Step 6: Return value if needed. Step 7: Call function with arguments. Step 8: Test with different inputs."
    },
    {
        "instruction": "implement a search filter function",
        "output": "Step 1: Get input value from search box. Step 2: Convert to lowercase for comparison. Step 3: Get array of items to filter. Step 4: Use filter method. Step 5: Check if item includes search term. Step 6: Return filtered results. Step 7: Update display with results. Step 8: Test with various queries."
    }
]

print(f"Adding {len(programming_examples)} programming examples to dataset...")

# Read existing dataset
with open('automation_dataset.jsonl', 'r', encoding='utf-8') as f:
    existing_data = [json.loads(line) for line in f]

print(f"Current dataset size: {len(existing_data)} examples")

# Combine existing and new examples
combined_data = existing_data + programming_examples

# Write updated dataset
with open('automation_dataset.jsonl', 'w', encoding='utf-8') as f:
    for example in combined_data:
        f.write(json.dumps(example, ensure_ascii=False) + '\n')

print(f"Updated dataset size: {len(combined_data)} examples")
print(f"✅ Added {len(programming_examples)} programming examples successfully!")
print("\nNext steps:")
print("1. Run: .\\venv\\Scripts\\python.exe scripts\\preprocess_automation.py")
print("2. Run: .\\venv\\Scripts\\python.exe run_training.py")
