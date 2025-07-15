import React, { useState, useEffect } from 'react';
import './App.css';
import ReactQuill from 'react-quill';
import 'react-quill/dist/quill.snow.css';

function App() {
  const [mails, setMails] = useState([]);
  const [selectedMail, setSelectedMail] = useState(null);
  const [showReplyBox, setShowReplyBox] = useState(false);
  const [replyContent, setReplyContent] = useState('');

  useEffect(() => {
    fetch('/api/messages')
      .then(res => res.json())
      .then(data => setMails(data));
  }, []);

  const handleReply = () => {
    if (!replyContent) return;
    fetch('/api/reply', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        mail_id: selectedMail.id,
        reply_content: replyContent
      })
    }).then(() => {
      alert('Réponse envoyée');
      setShowReplyBox(false);
      setReplyContent('');
    });
  };

  const getColor = importance => {
    if (importance === 'high') return 'red';
    if (importance === 'medium') return 'orange';
    return 'gray';
  };

  return (
    <div className="app">
      <h1>📬 Interface Mail</h1>
      <div className="mail-list">
        {mails.map(mail => (
          <div
            key={mail.id}
            className="mail-item"
            onClick={() => {
              setSelectedMail(mail);
              setShowReplyBox(false);
            }}
          >
            <div className="mail-header">
              <span className="dot" style={{ backgroundColor: getColor(mail.importance) }}></span>
              <strong>{mail.subject}</strong> — {mail.sender} ({mail.date})
            </div>
            <div className="mail-preview">
              {mail.body.slice(0, 120)}...
            </div>
          </div>
        ))}
      </div>

      {selectedMail && (
        <div className="mail-view">
          <h2>{selectedMail.subject}</h2>
          <p><strong>De :</strong> {selectedMail.sender}</p>
          <p><strong>Date :</strong> {selectedMail.date}</p>
          <p>{selectedMail.body}</p>

          {!showReplyBox && (
            <button onClick={() => setShowReplyBox(true)}>Répondre</button>
          )}

          {showReplyBox && (
            <div className="reply-box">
              <ReactQuill theme="snow" value={replyContent} onChange={setReplyContent} />
              <button onClick={handleReply}>Envoyer la réponse</button>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

export default App;
