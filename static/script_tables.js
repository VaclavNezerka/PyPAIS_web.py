// import activateExperiment from script.js
// import {activateExperiment} from './script.js';


function editExperimentId(id) {
    // Get the experiment id
    const uniqueQuery = '?nocache=' + new Date().getTime();
        fetch('/activate-experiment/' + id + uniqueQuery, { method: 'POST' })
        .then(response => response.json())
        .then(data => {
            if (data.status === 'success') {
                window.location.href = '/';
            }
        })
        .catch((error) => {
            console.error('Error:', error);
        });
}

