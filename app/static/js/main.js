/* ==============================================================================
 * app/static/js/main.js
 * ------------------------------------------------------------------------------
 * Main JavaScript file for client-side interactivity.
 * ============================================================================== */

// Execute this code only after the entire page has been loaded
document.addEventListener('DOMContentLoaded', function () {
    
    // --- Enhanced File Uploader Logic ---
    const fileInput = document.getElementById('fileInput');
    const uploaderBox = document.querySelector('.uploader-box');
    const uploaderForm = document.getElementById('uploaderForm');
    const submitButton = document.getElementById('submitButton');
    const buttonText = document.getElementById('buttonText');
    const buttonSpinner = document.getElementById('buttonSpinner');
    const uploaderLabel = document.querySelector('label[for=fileInput]');
    const originalLabelText = uploaderLabel ? uploaderLabel.textContent : 'یک فایل اکسل را انتخاب کنید یا اینجا بکشید';

    if (fileInput && uploaderBox) {
        // Function to prevent default browser behavior for drag/drop
        function preventDefaults(e) {
            e.preventDefault();
            e.stopPropagation();
        }

        // Add drag/drop event listeners to the uploader box
        ['dragenter', 'dragover', 'dragleave', 'drop'].forEach(eventName => {
            uploaderBox.addEventListener(eventName, preventDefaults, false);
        });

        // Add a 'highlight' class when a file is dragged over the box
        ['dragenter', 'dragover'].forEach(eventName => {
            uploaderBox.addEventListener(eventName, () => uploaderBox.classList.add('highlight'), false);
        });

        // Remove the 'highlight' class when the file leaves the box
        ['dragleave', 'drop'].forEach(eventName => {
            uploaderBox.addEventListener(eventName, () => uploaderBox.classList.remove('highlight'), false);
        });

        // Handle the file drop event
        uploaderBox.addEventListener('drop', handleDrop, false);

        function handleDrop(e) {
            let dt = e.dataTransfer;
            let files = dt.files;
            
            // Assign the dropped files to our file input element
            fileInput.files = files;

            // Manually trigger the 'change' event to update the UI
            fileInput.dispatchEvent(new Event('change'));
        }
        
        // Update the label text when a file is selected (either by click or drop)
        fileInput.addEventListener('change', function() {
            if (this.files && this.files.length > 0) {
                uploaderLabel.textContent = this.files[0].name;
            } else {
                uploaderLabel.textContent = originalLabelText;
            }
        });
    }
    
    // Show a loading spinner on the submit button when the form is submitted
    if (uploaderForm && submitButton) {
        uploaderForm.addEventListener('submit', function() {
            // Check for client-side validation first
            if (uploaderForm.checkValidity()) {
                submitButton.disabled = true;
                if (buttonText) buttonText.classList.add('d-none');
                if (buttonSpinner) buttonSpinner.classList.remove('d-none');
            }
        });
    }
});