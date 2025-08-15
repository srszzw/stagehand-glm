#!/bin/bash
# Run tests with coverage reporting

# Make sure we're in the right directory
cd "$(dirname "$0")"

# Install dev requirements if needed
if [[ -z $(pip3 list | grep pytest) ]]; then
  echo "Installing development requirements..."
  pip3 install -r requirements-dev.txt
fi

# Install package in development mode if needed
if [[ -z $(pip3 list | grep stagehand) ]]; then
  echo "Installing stagehand package in development mode..."
  pip3 install -e .
fi

# Run the tests
echo "Running tests with coverage..."
python3 -m pytest tests/ -v --cov=stagehand --cov-report=term --cov-report=html

echo "Tests complete. HTML coverage report is in htmlcov/ directory."

# Check if we should open the report
if [[ "$1" == "--open" || "$1" == "-o" ]]; then
  echo "Opening HTML coverage report..."
  if [[ "$OSTYPE" == "darwin"* ]]; then
    # macOS
    open htmlcov/index.html
  elif [[ "$OSTYPE" == "linux-gnu"* ]]; then
    # Linux with xdg-open
    xdg-open htmlcov/index.html
  elif [[ "$OSTYPE" == "msys" || "$OSTYPE" == "win32" ]]; then
    # Windows
    start htmlcov/index.html
  else
    echo "Couldn't automatically open the report. Please open htmlcov/index.html manually."
  fi
fi 