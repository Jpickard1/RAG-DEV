import React, { useState } from 'react';
import ChatContainer from './components/ChatContainer';
import LeftSideBar from './components/LeftSideBar';
import RightSideBar from './components/RightSideBar';
import './App.css';

function App() {
  const [messages, setMessages] = useState([]);  // Messages now managed in App
  const [showRightSidebar, setShowRightSidebar] = useState(false);  // Manage right sidebar visibility
  const [colorScheme, setColorScheme] = useState('light');  // Manage color scheme state

  const handleSendMessage = async (message) => {
    // Add the user's message to the message list
    setMessages([...messages, { id: Date.now(), text: message, process: null, sender: 'user' }]);
  
    let data = { message };
  
    try {
      // Call the backend API using fetch
      const response = await fetch('/api/invoke', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(data),
      });
  
      // Parse the JSON response
      const result = await response.json();
      let bot_response = result['response'] || '[No response]';
      let bot_log = result['response-log'] || '[No log]'; // You mentioned response-log for the process
      console.log(`bot_response= ${bot_response}`)
      console.log(`bot_log= ${bot_log}`)
      // Add the bot's response to the message list, including both text and process
      setMessages((prevMessages) => [
        ...prevMessages, 
        { id: Date.now(), text: bot_response, process: bot_log, sender: 'bot' }
      ]);
    } catch (error) {
      console.error('Error:', error);
    }
  };  

  const toggleRightSidebar = () => {
    setShowRightSidebar(!showRightSidebar);  // Toggle sidebar visibility
  };

  return (
    <div className="App">
      <header className="App-header">
        <h2>{String.fromCodePoint('0x1f916')} BRAD </h2>
        <button className="sidebar-toggle" onClick={toggleRightSidebar}>
          {showRightSidebar ? 'Close Settings' : 'Open Settings'}
        </button>  {/* Button to toggle RightSideBar */}
      </header>
      <div className="Main-container">
        <LeftSideBar setMessages={setMessages}/>
        {/* Pass messages and handleSendMessage to ChatContainer */}
        <ChatContainer messages={messages} onSendMessage={handleSendMessage} />
        {showRightSidebar && <RightSideBar setColorScheme={setColorScheme} />} {/* Conditionally render RightSideBar */}

      </div>
    </div>
  );
}

export default App;
