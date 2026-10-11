// The ShubhLabh WhatsApp number and join code, in ONE place. Change them here and every page, button and QR code follows.
// (The How-to screenshots and the tutorial video show them too: re-run scripts/capture_howto.py and re-render whatsapp.mp4 after a change.)
export const WA_NUMBER_DISPLAY = '+1 415 523 8886';
export const WA_NUMBER_E164 = '14155238886';
/** The first message a new user sends, exactly as typed. */
export const WA_JOIN_TEXT = 'join bright-blanket';
/** Click-to-chat: opens the WhatsApp app on a phone, WhatsApp Desktop or Web on a computer, with the join message typed in. */
export const WA_LINK = `https://wa.me/${WA_NUMBER_E164}?text=${encodeURIComponent(WA_JOIN_TEXT)}`;
