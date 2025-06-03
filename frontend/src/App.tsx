import { useEffect, useState } from 'react';

export default function App() {
  const [up, setUp] = useState(false);

  useEffect(() => {
    fetch('/healthz').then((res) => {
      if (res.status === 204) {
        setUp(true);
      }
    });
  }, []);

  return (
    <div className="p-4 text-center">
      {up ? '🎉 Lie-Ability server is UP' : 'Checking server...'}
    </div>
  );
}
