function uploadFiles(filesUploaded) {
    let files = Array.from(filesUploaded);    
    return new Promise(async (resolve, reject) => {
        try {
            for (let i = 0; i < files.length; i++) {
                console.log('Uploading file...', i);
                const formData = new FormData();
                formData.append('file', files[i]);
            await fetch('/backup-storage', { method: 'GET' });
            await Promise.all([
                fetch('/remove-background', { method: 'POST', body: formData }),
                fetch('/grayscale-data', { method: 'POST', body: formData }),
            ])
            await fetch('/entropy', { method: 'POST', body: formData })
            await fetch('/apply-mask', { method: 'POST' });
            await fetch('/save?status=processing', { method: 'POST' }).catch((error) => {
                console.error('Error:', error);
            });
            await fetch('/restore-storage', { method: 'GET' });        
            self.postMessage('report');
        }
        // send a message back to the main thread
        // window.location.reload();
        resolve();
    }
     catch (error) {
        reject(error);
    }    
    });
}


self.onmessage = function(e) {
    uploadFiles(e.data.filesUploaded)
    .then(() => {
        self.postMessage('success');
    })
    .catch((error) => {
        self.postMessage('error');
    });
}
