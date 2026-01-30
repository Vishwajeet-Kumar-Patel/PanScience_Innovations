#!/bin/bash
# Coverage Report Generator for PanScience Innovations
# This script runs tests and generates HTML coverage report

echo "🧪 PanScience Innovations - Test Coverage Generator"
echo "=================================================="
echo ""

# Navigate to backend directory
cd backend || exit

echo "📦 Installing test dependencies..."
pip install -q pytest pytest-cov pytest-asyncio coverage-badge

echo ""
echo "🧪 Running test suite with coverage..."
pytest --cov=app \
       --cov-report=html \
       --cov-report=term-missing \
       --cov-report=xml \
       --cov-fail-under=95 \
       -v

# Check if tests passed
if [ $? -eq 0 ]; then
    echo ""
    echo "✅ All tests passed! Coverage requirement met (95%+)"
    echo ""
    
    # Generate coverage badge
    echo "🎨 Generating coverage badge..."
    coverage-badge -o coverage.svg -f
    
    echo ""
    echo "📊 Coverage Report Generated!"
    echo "   HTML Report: backend/htmlcov/index.html"
    echo "   XML Report:  backend/coverage.xml"
    echo "   Badge:       backend/coverage.svg"
    echo ""
    echo "To view the HTML report, run:"
    echo "   start backend/htmlcov/index.html  (Windows)"
    echo "   open backend/htmlcov/index.html   (macOS)"
    echo "   xdg-open backend/htmlcov/index.html (Linux)"
else
    echo ""
    echo "❌ Tests failed or coverage below 95%"
    echo "   Please fix failing tests or add more test coverage"
    exit 1
fi
