#!/bin/bash

# --- Configuration ---
# !!! IMPORTANT: Replace LATEST_VERSION_HERE with the latest version from the NoMachine website !!!
# Example: VERSION="8.16.1_1"
VERSION="8.16.1_1"
ARCH="amd64" # Assuming standard 64-bit architecture for Debian 12. Check with `uname -m` if unsure.
# --- End Configuration ---

# Construct download URL and package name
# Example URL structure from source [6]
MAJOR_MINOR_VERSION=$(echo "$VERSION" | cut -d'.' -f1,2)
PACKAGE_NAME="nomachine_${VERSION}_${ARCH}.deb"
DOWNLOAD_URL="https://download.nomachine.com/download/${MAJOR_MINOR_VERSION}/Linux/${PACKAGE_NAME}"

echo "--- NoMachine Installer Script ---"
echo "Attempting to download NoMachine version ${VERSION} for ${ARCH}"
echo "Download URL: ${DOWNLOAD_URL}"

# Download the package
echo "Downloading package..."
wget -O "$PACKAGE_NAME" "$DOWNLOAD_URL"

# Check if download was successful
if [ $? -ne 0 ]; then
  echo "ERROR: Download failed. Please check the VERSION and ARCH variables, and your internet connection."
  exit 1
fi

echo "Download complete: ${PACKAGE_NAME}"

# Install the package using apt (handles dependencies better than dpkg alone)
# Installation commands based on sources [4, 5, 6, 7, 10, 12, 15]
echo "Installing NoMachine using apt..."
sudo apt update # Optional: Update package list first
sudo apt install "./${PACKAGE_NAME}" -y # The ./ is important to specify the local file

# Check if installation was successful
if [ $? -ne 0 ]; then
  echo "ERROR: Installation failed. Please check the output above for errors."
  # Optional: Clean up the downloaded file even on failure?
  # echo "Cleaning up downloaded file: ${PACKAGE_NAME}"
  # rm "$PACKAGE_NAME"
  exit 1
fi

echo "NoMachine installation completed successfully!"

# Clean up the downloaded package
echo "Cleaning up downloaded file: ${PACKAGE_NAME}"
rm "$PACKAGE_NAME"

echo "--- Script Finished ---"
exit 0