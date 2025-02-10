// this function converts a base64 string to a blob
// the images are in a str64 format and it is decoded as a utf-8 string
// we need to convert them to a blob
export default function base64toBlob(base64, type) {
    var byteString = atob(base64);
    var ab = new ArrayBuffer(byteString.length);
    var ia = new Uint8Array(ab);
    for (var i = 0; i < byteString.length; i++) {
        ia[i] = byteString.charCodeAt(i);
    }
    return new Blob([ab], { type: type });
}