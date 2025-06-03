import { useEffect, useState } from 'react';

interface Player {
  id: string;
  nickname: string;
  avatar: string;
}

export default function Host() {
  const [code, setCode] = useState<string | null>(null);
  const [token, setToken] = useState<string | null>(null);
  const [players, setPlayers] = useState<Player[]>([]);
  const [ws, setWs] = useState<WebSocket | null>(null);

  const createLobby = async () => {
    const res = await fetch('/api/v1/lobbies', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ roundCount: 3 })
    });
    if (res.ok) {
      const data = await res.json();
      setCode(data.code);
      setToken(data.hostToken);
    }
  };

  const startGame = async () => {
    if (!code || !token) return;
    await fetch(`/api/v1/lobbies/${code}/start`, {
      method: 'POST',
      headers: { Authorization: `Bearer ${token}` }
    });
  };

  useEffect(() => {
    if (!code || !token || ws) return;
    const socket = new WebSocket(`/ws/lobbies/${code}?token=${token}`);
    socket.onmessage = (e) => {
      const msg = JSON.parse(e.data);
      if (msg.type === 'lobby_update') {
        setPlayers(msg.payload.players);
      }
    };
    setWs(socket);
    return () => socket.close();
  }, [code, token, ws]);

  if (!code) {
    return (
      <div className="p-4 text-center">
        <button onClick={createLobby}>Create Lobby</button>
      </div>
    );
  }

  return (
    <div className="p-4 text-center">
      <h1>Lobby {code}</h1>
      <ul className="my-4">
        {players.map((p) => (
          <li key={p.id}>{p.nickname}</li>
        ))}
      </ul>
      <button onClick={startGame} disabled={players.length < 2}>
        Start Game
      </button>
    </div>
  );
}
