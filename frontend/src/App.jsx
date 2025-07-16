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
import React, { useState, useEffect } from "react";

function App() {
  const [messages, setMessages] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    fetch("/api/messages")
      .then((res) => res.json())
      .then((data) => {
        setMessages(data);
        setLoading(false);
      })
      .catch((err) => {
        setError(err.message);
        setLoading(false);
      });
  }, []);

  if (loading) return <div>Chargement…</div>;
  if (error) return <div>Erreur : {error}</div>;

  return (
    <div className="App">
      <h1>Liste des emails</h1>
      <ul>
        {messages.map((msg) => (
          <li key={msg.id + msg.mailbox} style={{ marginBottom: 16, border: '1px solid #ccc', padding: 8 }}>
            <strong>{msg.subject}</strong> <br />
            <span>De : {msg.sender}</span> <br />
            <span>Date : {msg.date}</span> <br />
            <span>Importance : {msg.importance}</span> <br />
            <span>Score : {msg.score}</span> <br />
            <span style={{ color: '#0074D9' }}>Boîte : {msg.mailbox}</span> <br />
            <div style={{ marginTop: 8 }}>{msg.body}</div>
          </li>
        ))}
      </ul>
    </div>
  );
}

export default App;
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
