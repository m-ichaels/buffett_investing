import subprocess
import sys

# List of scripts to run in order
year = 2021

scripts = [
    'step1a.py',
    'step1b.py',
    'step2.py',
    'step3.py',
    'step4.py',
    'step5.py',
    'step6.py',
    'step7.py',
    'step8.py',
    'step9.py',
    'step10.py'
]

# Execute each script sequentially
for script in scripts:
    print(f"Running {script}...")
    try:
        # Run the script using the current Python interpreter, raise an exception if it fails
        subprocess.run([sys.executable, script], check=True)
        print(f"{script} completed successfully")
    except subprocess.CalledProcessError as e:
        # If a script fails, print an error and stop execution
        print(f"Error: {script} failed with return code {e.returncode}")
        break
else:
    # This block runs only if all scripts complete successfully (no break)
    print("All scripts completed successfully")