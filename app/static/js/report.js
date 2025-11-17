// ==============================================================================
// app/static/js/report.js
// ------------------------------------------------------------------------------
// JavaScript for the main report page interactivity, including filtering,
// chart rendering, and dynamic link updates. It consumes the `frontendData`
// object that is embedded in the report.html template.
// ==============================================================================

document.addEventListener('DOMContentLoaded', function () {
    
    // --- Global Variables ---
    let performanceChart = null; // To hold the Chart.js instance
    const personFilters = document.querySelectorAll('.person-filter');
    const selectAllCheckbox = document.getElementById('selectAllCheckbox');
    const pdfLink = document.getElementById('pdfExportLink');
    const colors = ["#3f51b5", "#e53935", "#fb8c00", "#43a047", "#1e88e5", "#8e24aa", "#00897b", "#fdd835", "#d81b60", "#6d4c41"];

    // --- Main Execution on Page Load ---
    if (typeof frontendData !== 'undefined' && frontendData) {
        initializeChart();
        initializeFilters();
        updateFilters(); // Run once on load to set the initial state
    } else {
        console.error("Frontend data object not found. Cannot initialize report interactivity.");
    }


    // ==========================================================================
    // CHART INITIALIZATION
    // ==========================================================================
    function initializeChart() {
        const ctx = document.getElementById('performanceChart')?.getContext('2d');
        if (!ctx) {
            console.error("Chart canvas element not found.");
            return;
        }

        const chartData = frontendData.chartData;
        const datasets = [];

        // 1. Add Total Sales Dataset
        datasets.push({
            label: 'کل فروش ماهانه',
            data: chartData.datasets.total_sales,
            borderColor: colors[0],
            backgroundColor: colors[0],
            borderWidth: 3,
            tension: 0.3,
            fill: false,
            order: 0 // Ensure this line is drawn on top
        });

        // 2. Add Team Target Dataset
        datasets.push({
            label: 'هدف جمعی',
            data: chartData.datasets.targets,
            borderColor: colors[1],
            backgroundColor: colors[1],
            borderWidth: 2,
            borderDash: [5, 5], // Make it a dashed line
            tension: 0.3,
            fill: false,
            order: 1
        });

        // 3. Add Datasets for each person
        let colorIndex = 2;
        for (const person in chartData.datasets.persons) {
            datasets.push({
                label: person,
                data: chartData.datasets.persons[person],
                borderColor: colors[colorIndex % colors.length],
                backgroundColor: colors[colorIndex % colors.length],
                borderWidth: 1.5,
                tension: 0.3,
                fill: false,
                hidden: false, // Initially all are visible
                order: 2
            });
            colorIndex++;
        }

        performanceChart = new Chart(ctx, {
            type: 'line',
            data: {
                labels: chartData.labels,
                datasets: datasets
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    tooltip: {
                        callbacks: {
                            label: function (context) {
                                return context.dataset.label + ': ' + new Intl.NumberFormat('fa-IR').format(context.parsed.y) + ' تومان';
                            }
                        }
                    },
                    legend: {
                        position: 'top',
                    },
                },
                scales: {
                    y: {
                        ticks: {
                            callback: function (value) {
                                return new Intl.NumberFormat('fa-IR').format(value);
                            }
                        }
                    }
                }
            }
        });
    }

    // ==========================================================================
    // FILTER INITIALIZATION AND MASTER UPDATE LOGIC
    // ==========================================================================
    function initializeFilters() {
        personFilters.forEach(checkbox => {
            checkbox.addEventListener('change', updateFilters);
        });

        if (selectAllCheckbox) {
            selectAllCheckbox.addEventListener('change', function() {
                personFilters.forEach(checkbox => {
                    checkbox.checked = this.checked;
                });
                updateFilters();
            });
        }
    }

    function updateFilters() {
        const selectedPeople = Array.from(personFilters)
                                    .filter(cb => cb.checked)
                                    .map(cb => cb.value);

        const allPeople = frontendData.personList;
        // If nothing is selected, behave as if nothing should be shown.
        const peopleToShow = selectedPeople;
        
        // Update "Select All" checkbox state
        if (selectAllCheckbox) {
             selectAllCheckbox.checked = peopleToShow.length === allPeople.length;
        }

        // --- 1. Filter the Overall Summary Table ---
        const summaryTableBody = document.getElementById('summary-table-body');
        if (summaryTableBody) {
            summaryTableBody.querySelectorAll('tr[data-person-name]').forEach(row => {
                const personName = row.dataset.personName;
                row.style.display = peopleToShow.includes(personName) ? '' : 'none';
            });
        }

        // --- 2. Filter the Detailed Report and Person-Monthly Report items ---
        document.querySelectorAll('.report-person-item').forEach(item => {
            const personName = item.dataset.personName;
            item.style.display = peopleToShow.includes(personName) ? '' : 'none';
        });

        // --- 3. Filter the Chart ---
        if (performanceChart) {
            // Recalculate total sales based on selection
            const newTotalSales = frontendData.chartData.labels.map((_, monthIndex) => {
                let monthlySum = 0;
                peopleToShow.forEach(person => {
                    // Check if person exists in chart data to prevent errors
                    if (frontendData.chartData.datasets.persons[person]) {
                        monthlySum += frontendData.chartData.datasets.persons[person][monthIndex];
                    }
                });
                return monthlySum;
            });

            // Update total sales dataset (which is always the first one)
            performanceChart.data.datasets[0].data = newTotalSales;
            
            // Show/hide individual person datasets
            performanceChart.data.datasets.forEach(dataset => {
                // Ignore the "Total" and "Target" lines
                if (dataset.label !== 'کل فروش ماهانه' && dataset.label !== 'هدف جمعی') {
                    dataset.hidden = !peopleToShow.includes(dataset.label);
                }
            });

            performanceChart.update();
        }

        // --- 4. Dynamically Update the PDF Export Link ---
       if (pdfLink) {
           const baseUrl = pdfLink.getAttribute('data-base-url');
           if (peopleToShow.length > 0 && peopleToShow.length < allPeople.length) {
               // If a specific subset is selected, add the filter
               pdfLink.href = baseUrl + '?filter=' + encodeURIComponent(peopleToShow.join(','));
           } else {
               // If all or none are selected, link to a version with no filter (which means all)
               pdfLink.href = baseUrl;
           }
       }
    }
});