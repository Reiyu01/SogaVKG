import { useState, useRef, useEffect } from 'react';

const ASK_API_URL = 'http://127.0.0.1:8000/query/ask';

function ResultTable({ rows }) {
  const columns = rows.length > 0 ? Object.keys(rows[0]) : [];

  if (rows.length === 0) {
    return <div style={{ color: '#888', fontSize: '13px' }}>沒有符合的資料</div>;
  }

  return (
    <div style={{ overflowX: 'auto' }}>
      <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '12px' }}>
        <thead>
          <tr>
            {columns.map((col) => (
              <th
                key={col}
                style={{
                  textAlign: 'left',
                  borderBottom: '1.5px solid #ddd',
                  padding: '6px 8px',
                  background: '#fafafa',
                  whiteSpace: 'nowrap',
                }}
              >
                {col}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row, i) => (
            <tr key={i}>
              {columns.map((col) => (
                <td
                  key={col}
                  style={{ borderBottom: '1px solid #eee', padding: '6px 8px', whiteSpace: 'nowrap' }}
                >
                  {row[col] === null ? <span style={{ color: '#ccc' }}>—</span> : String(row[col])}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function UserBubble({ text }) {
  return (
    <div style={{ display: 'flex', justifyContent: 'flex-end', marginBottom: '12px' }}>
      <div
        style={{
          background: '#185fa5',
          color: 'white',
          padding: '10px 16px',
          borderRadius: '14px 14px 2px 14px',
          maxWidth: '70%',
          fontSize: '14px',
        }}
      >
        {text}
      </div>
    </div>
  );
}

function AssistantBubble({ item }) {
  return (
    <div style={{ display: 'flex', justifyContent: 'flex-start', marginBottom: '20px' }}>
      <div
        style={{
          background: '#f1efe8',
          padding: '14px 16px',
          borderRadius: '14px 14px 14px 2px',
          maxWidth: '85%',
          width: item.chatReply ? 'auto' : '100%',
        }}
      >
        {item.loading && (
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: '13px', color: '#888' }}>
            <span
              style={{
                width: 14,
                height: 14,
                border: '2px solid #ccc',
                borderTopColor: '#185fa5',
                borderRadius: '50%',
                display: 'inline-block',
                animation: 'spin 0.6s linear infinite',
              }}
            />
            思考中...
          </div>
        )}

        {item.error && (
          <div style={{ color: '#993c1d', fontSize: '13px' }}>
            查詢失敗{item.attempts ? `（嘗試 ${item.attempts} 次）` : ''}：{item.error}
          </div>
        )}

        {/* 純聊天回覆 */}
        {item.chatReply && (
          <div style={{ fontSize: '14px', whiteSpace: 'pre-wrap' }}>{item.chatReply}</div>
        )}

        {/* 查詢結果 */}
        {item.success && item.result && (
          <>
            <div style={{ fontSize: '13px', color: '#5f5e5a', marginBottom: '8px' }}>
              找到 {item.result.count} 筆結果
              {item.attempts > 1 && `（重試了 ${item.attempts - 1} 次）`}
            </div>

            <ResultTable rows={item.result.data} />

            <details style={{ marginTop: '10px', fontSize: '12px' }}>
              <summary style={{ cursor: 'pointer', color: '#888' }}>查看查詢細節</summary>
              <pre
                style={{
                  background: 'white',
                  padding: '10px',
                  borderRadius: 6,
                  overflowX: 'auto',
                  fontSize: '11px',
                  marginTop: '6px',
                }}
              >
                {JSON.stringify(item.translatedQuery, null, 2)}
              </pre>
            </details>
          </>
        )}
      </div>
    </div>
  );
}

// function AssistantBubble({ item }) {
//   return (
//     <div style={{ display: 'flex', justifyContent: 'flex-start', marginBottom: '20px' }}>
//       <div
//         style={{
//           background: '#f1efe8',
//           padding: '14px 16px',
//           borderRadius: '14px 14px 14px 2px',
//           maxWidth: '85%',
//           width: '100%',
//         }}
//       >
//         {item.loading && (
//           <div style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: '13px', color: '#888' }}>
//             <span
//               style={{
//                 width: 14,
//                 height: 14,
//                 border: '2px solid #ccc',
//                 borderTopColor: '#185fa5',
//                 borderRadius: '50%',
//                 display: 'inline-block',
//                 animation: 'spin 0.6s linear infinite',
//               }}
//             />
//             思考中...
//           </div>
//         )}

//         {item.error && (
//           <div style={{ color: '#993c1d', fontSize: '13px' }}>
//             查詢失敗{item.attempts ? `（嘗試 ${item.attempts} 次）` : ''}：{item.error}
//           </div>
//         )}

//         {item.success && (
//           <>
//             <div style={{ fontSize: '13px', color: '#5f5e5a', marginBottom: '8px' }}>
//               找到 {item.result.count} 筆結果
//               {item.attempts > 1 && `（重試了 ${item.attempts - 1} 次）`}
//             </div>

//             <ResultTable rows={item.result.data} />

//             <details style={{ marginTop: '10px', fontSize: '12px' }}>
//               <summary style={{ cursor: 'pointer', color: '#888' }}>查看查詢細節</summary>
//               <pre
//                 style={{
//                   background: 'white',
//                   padding: '10px',
//                   borderRadius: 6,
//                   overflowX: 'auto',
//                   fontSize: '11px',
//                   marginTop: '6px',
//                 }}
//               >
//                 {JSON.stringify(item.translatedQuery, null, 2)}
//               </pre>
//             </details>
//           </>
//         )}
//       </div>
//     </div>
//   );
// }

export default function AskPage() {
  const [question, setQuestion] = useState('');
  const [messages, setMessages] = useState([]);

  const bottomRef = useRef(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  const handleSubmit = async () => {
    const q = question.trim();
    if (!q) return;

    setQuestion('');

    setMessages((prev) => [
      ...prev,
      { type: 'user', text: q },
      { type: 'assistant', loading: true },
    ]);

    try {
      const res = await fetch(ASK_API_URL, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ question: q }),
      });

      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      
        const data = await res.json();

        setMessages((prev) => {
        const updated = [...prev];
        const lastIndex = updated.length - 1;

        if (data.type === 'chat') {
            updated[lastIndex] = {
            type: 'assistant',
            chatReply: data.reply,
            };
        } else if (data.success) {
            updated[lastIndex] = {
            type: 'assistant',
            success: true,
            attempts: data.attempts,
            result: data.result,
            translatedQuery: data.translated_query,
            };
        } else {
            updated[lastIndex] = {
            type: 'assistant',
            error: data.error,
            attempts: data.attempts,
            };
        }

        return updated;
        });


    //   const data = await res.json();

    //   setMessages((prev) => {
    //     const updated = [...prev];
    //     const lastIndex = updated.length - 1;

    //     if (data.success) {
    //       updated[lastIndex] = {
    //         type: 'assistant',
    //         success: true,
    //         attempts: data.attempts,
    //         result: data.result,
    //         translatedQuery: data.translated_query,
    //       };
    //     } else {
    //       updated[lastIndex] = {
    //         type: 'assistant',
    //         error: data.error,
    //         attempts: data.attempts,
    //       };
    //     }

    //     return updated;
    //   });
    } catch (err) {
      setMessages((prev) => {
        const updated = [...prev];
        updated[updated.length - 1] = { type: 'assistant', error: err.message };
        return updated;
      });
    }
  };

  return (
    <div
      style={{
        flex: 1,
        height: '100vh',
        display: 'flex',
        flexDirection: 'column',
        boxSizing: 'border-box',
      }}
    >
      <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>

      <div style={{ padding: '20px 40px 12px', borderBottom: '1px solid #eee' }}>
        <h2 style={{ margin: 0 }}>AI 檢索</h2>
        <p style={{ color: '#888', fontSize: '13px', margin: '4px 0 0' }}>
          用一般中文描述你想查詢的內容
        </p>
      </div>

      <div style={{ flex: 1, overflowY: 'auto', padding: '20px 40px' }}>
        {messages.length === 0 && (
          <div style={{ color: '#ccc', fontSize: '14px', textAlign: 'center', marginTop: '60px' }}>
            試著問問看，例如「C217 有哪些感測器類的資產」
          </div>
        )}

        {messages.map((msg, i) =>
          msg.type === 'user' ? (
            <UserBubble key={i} text={msg.text} />
          ) : (
            <AssistantBubble key={i} item={msg} />
          )
        )}

        <div ref={bottomRef} />
      </div>

      <div
        style={{
          display: 'flex',
          gap: '10px',
          padding: '16px 40px',
          borderTop: '1px solid #eee',
        }}
      >
        <input
          type="text"
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === 'Enter') handleSubmit();
          }}
          placeholder="輸入你的問題..."
          style={{
            flex: 1,
            padding: '10px 14px',
            border: '1px solid #ddd',
            borderRadius: 8,
            fontSize: '14px',
          }}
        />
        <button
          onClick={handleSubmit}
          style={{
            padding: '10px 20px',
            border: 'none',
            borderRadius: 8,
            background: '#185fa5',
            color: 'white',
            fontSize: '14px',
            cursor: 'pointer',
          }}
        >
          送出
        </button>
      </div>
    </div>
  );
}