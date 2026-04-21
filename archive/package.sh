#!/bin/bash
# Package script for ClawHub publishing

set -e

echo "📦 Packaging Ave Accumulation Monitor for ClawHub..."

# Check if we're in the right directory
if [ ! -f "SKILL.md" ]; then
    echo "❌ Error: SKILL.md not found. Run this from skill root directory."
    exit 1
fi

# Create package directory
PACKAGE_DIR="ave-accumulation-monitor-v1.0.0"
rm -rf "$PACKAGE_DIR"
mkdir -p "$PACKAGE_DIR"

# Copy required files
echo "📁 Copying files..."
cp SKILL.md "$PACKAGE_DIR/"
cp README.md "$PACKAGE_DIR/" 2>/dev/null || echo "⚠️ README.md not found"
cp package.json "$PACKAGE_DIR/" 2>/dev/null || echo "⚠️ package.json not found"
cp LICENSE "$PACKAGE_DIR/" 2>/dev/null || echo "⚠️ LICENSE not found"

# Copy scripts
if [ -d "scripts" ]; then
    cp -r scripts "$PACKAGE_DIR/"
fi

# Copy other Python files
for file in *.py; do
    if [ -f "$file" ]; then
        cp "$file" "$PACKAGE_DIR/"
    fi
done

# Create tar.gz archive
echo "🗜️  Creating archive..."
tar -czf "${PACKAGE_DIR}.tar.gz" "$PACKAGE_DIR"

# Create .skill file (zip with .skill extension)
echo "📦 Creating .skill package..."
cd "$PACKAGE_DIR"
zip -r "../ave-accumulation-monitor-v1.0.0.skill" .
cd ..

# Cleanup
rm -rf "$PACKAGE_DIR"

echo ""
echo "✅ Package created successfully!"
echo ""
echo "Files created:"
echo "  📄 ave-accumulation-monitor-v1.0.0.tar.gz"
echo "  📦 ave-accumulation-monitor-v1.0.0.skill"
echo ""
echo "To publish to ClawHub:"
echo "  clawhub publish ./ave-accumulation-monitor-v1.0.0.skill \\"
echo "    --slug ave-accumulation-monitor \\"
echo "    --name \"Ave Accumulation Monitor\" \\"
echo "    --version 1.0.0 \\"
echo "    --changelog \"Initial release\""
echo ""
