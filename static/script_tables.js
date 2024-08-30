// import save from script.js
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

function exportExperimentPDF(id) {
    // Get the experiment id
    console.warn('Exporting experiment PDF is not yet implemented. THE FORMAT WAS NOT DEFINED');
}

function deleteExperimentId(id) {
    // Get the experiment id
    const uniqueQuery = '?nocache=' + new Date().getTime();
        fetch('/delete-experiment/' + id + uniqueQuery, { method: 'POST' })
        .then(response => response.json())
        .then(data => {
            if (data.status === 'success') {
                window.location.reload();;
            }
        })
        .catch((error) => {
            console.error('Error:', error);
        });
}

function callQueryStringURL(queryString) {
    // Get the query string
    window.location.search = queryString;
}

function excludeFromSearchQuery(queryKey) {
    const currentQueryString = window.location.search;
    const keys = currentQueryString.split('&').map(key => key.split('=')[0]);
    if (keys.includes(queryKey)) {
        const newQueryString = currentQueryString.replace(queryKey + '=' + currentQueryString.split(queryKey + '=')[1].split('&')[0], '');
        callQueryStringURL(newQueryString);
    }
}

function concatenateSearchQuery(queryString) {
            const key = queryString.split('=')[0]+"=";
            const value = queryString.split('=')[1].split('&')[0];  
            const currentQueryString = window.location.search;

            // current query keys
            let noQuestionMark = currentQueryString.split('?')[1];
            if (noQuestionMark == undefined) {
               noQuestionMark = currentQueryString;
            }
            const keys = noQuestionMark.split('&').map(key => key.split('=')[0]+"=");
            // if any key == queryString key, replace the value
            let newQueryString = '';
            if (keys.includes(key)) {
                id=keys.indexOf(key);
                const currentValue = currentQueryString.split(keys[id])[1].split('&')[0];
                newQueryString = currentQueryString.replace(keys[id] + currentValue, key + value);
            } else {
                newQueryString = currentQueryString + '&' + queryString;
            }
            callQueryStringURL(newQueryString);
}

document.getElementById('previous_page').addEventListener('click', function() {
    current_page = parseInt(document.getElementById('current_page').innerText);
    if (current_page == 1) {
        current_page = 1;
    } else {
        current_page -= 1;
    }
    document.getElementById('current_page').innerText = current_page;
    concatenateSearchQuery('page=' + current_page);
});
document.getElementById('next_page').addEventListener('click', function() {
    current_page = parseInt(document.getElementById('current_page').innerText);
    current_page += 1;
    document.getElementById('current_page').innerText = current_page;
    concatenateSearchQuery('page=' + current_page);
});

document.getElementById('sortBy').addEventListener('change', function() {
    const sortBy = this.value;
    instructions = sortBy.replace(/\s+/g,"").split(',');
    sort_order="";
    for (let i = 0; i < instructions.length; i++) {
        switch (instructions[i].toLowerCase()) {
        case "id": sort_order += "id,"; break;
        case "asphaltratio": sort_order += "asphalt_ratio,"; break;
        case "expertguess": sort_order += "expert_guess,"; break;
        case "date": sort_order += "time_stamp,"; break;
        case "state": sort_order += "current_state,"; break;
        default: break;
        }
    }
    sort_order = sort_order.slice(0, -1);
    if (sort_order=="") {   
        excludeFromSearchQuery('sort_by');
    } else {
        concatenateSearchQuery('sort_by=' + sort_order);
    }   
});


document.getElementById('maxRecords').addEventListener('change', function() {
    const maxRecords = this.value;
    concatenateSearchQuery('page_limit=' + maxRecords);
});

document.getElementById('sortOrder').addEventListener('change', function() {
    const sortOrder = this.value;
    concatenateSearchQuery('sort_order=' + sortOrder);
});

document.addEventListener('DOMContentLoaded', function() {
    // Restore any other field states as necessary (e.g., input values, checkboxes)
    
    // Get query parameters from the URL
    const urlParams = new URLSearchParams(window.location.search);

    // Restore page number
    const page = urlParams.get('page');
    if (page) {
        document.getElementById('current_page').innerText = page;
    }
    // Restore sort order
    const sortBy = urlParams.get('sort_by');
    if (sortBy) {
        dictionary = {
            'id': 'id',
            'asphalt_ratio': 'Asphalt Ratio',
            'expert_guess': 'Expert Guess',
            'time_stamp': 'Date',
            'current_state': 'State'
        };
        document.getElementById('sortBy').value = sortBy.split(',').map(key => dictionary[key]).join(', ');
    }
    const maxRecords = Number(urlParams.get('page_limit'));
    if (maxRecords) {
        document.getElementById('maxRecords').value = maxRecords;
    }
    const sortOrder = urlParams.get('sort_order');
    if (sortOrder) {
        document.getElementById('sortOrder').value = sortOrder;
    }
});

document.getElementById('fileInput').addEventListener('change', async function() {
    // uploadFiles;
    files = Array.from(this.files);
    
    for (let i = 0; i < files.length; i++) {
        const formData = new FormData();
        formData.append('file', files[i]);
        console.log('Uploading file...', i);
        await fetch('/backup-storage', { method: 'POST' });
        await Promise.all([
            fetch('/remove-background', { method: 'POST', body: formData }),
            fetch('/grayscale-data', { method: 'POST', body: formData }),
        ])
        await fetch('/entropy', { method: 'POST', body: formData })
        await fetch('/apply-mask', { method: 'POST' });
        await fetch('/save?status=processing', { method: 'POST' }).catch((error) => {
            console.error('Error:', error);
        });
        await fetch('restore-storage', { method: 'POST' });        
    }
    window.location.reload();
});