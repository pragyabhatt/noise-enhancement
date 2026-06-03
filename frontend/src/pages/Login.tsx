import { useAuth } from '../hooks/useAuth';
import { useToast } from '../components/Toast';

const Login: React.FC = () => {
  const navigate = useNavigate();
  const [credentials, setCredentials] = useState({ username: '', password: '' });
  const [error, setError] = useState('');
  const { trigger } = useToast();

  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    setCredentials({ ...credentials, [e.target.name]: e.target.value });
  };

const { login } = useAuth();
    const handleSubmit = async (e: React.FormEvent) => {
      e.preventDefault();
      try {
        await login(credentials.username, credentials.password);
        navigate('/dashboard');
      } catch (err: any) {
        const msg = err.message || 'Login failed';
        setError(msg);
        trigger(msg, 'error');
      }
    };

  return (
    <div className="login-container flex items-center justify-center min-h-screen bg-[#0f172a]">
      <div className="login-card bg-[#1e293b] bg-opacity-80 backdrop-filter backdrop-blur-md p-8 rounded-xl border border-[#00e5ff] hover:border-[#10b981] transition-colors duration-300 animate-pulse-on-hover">
        <h1 className="login-title text-3xl font-bold text-center text-[#00e5ff] mb-2">
          🔐 DEAL - Defence Audio Enhancement & Evaluation
        </h1>
        <p className="text-sm text-center text-[#e0e7ff] mb-4">
          Tactical Intelligence Analysis System | Secure Offline Processing
        </p>
        <div className="flex justify-center space-x-2 mb-4">
          <span className="status-indicator bg-green-500 rounded-full w-3 h-3 animate-pulse" title="System Ready" />
          <span className="status-indicator bg-green-500 rounded-full w-3 h-3 animate-pulse" title="Encryption AES-256" />
          <span className="status-indicator bg-green-500 rounded-full w-3 h-3 animate-pulse" title="Air‑Gapped" />
        </div>
        {error && <div className="error-message text-red-400 mb-2 text-center">{error}</div>}
        <form onSubmit={handleSubmit} className="flex flex-col space-y-4">
          <input
            name="username"
            type="text"
            placeholder="Username"
            value={credentials.username}
            onChange={handleChange}
            required
            className="bg-[#2c2c3d] text-[#e0e7ff] p-2 rounded focus:outline-none focus:ring-2 focus:ring-[#00e5ff]"
          />
          <input
            name="password"
            type="password"
            placeholder="Password"
            value={credentials.password}
            onChange={handleChange}
            required
            className="bg-[#2c2c3d] text-[#e0e7ff] p-2 rounded focus:outline-none focus:ring-2 focus:ring-[#00e5ff]"
          />
          <button
            type="submit"
            className="login-button bg-gradient-to-r from-[#00e5ff] to-[#10b981] text-[#0f172a] font-semibold py-2 rounded hover:from-[#10b981] hover:to-[#00e5ff] transition-all"
          >
            ▶ Authenticate Access ◀
          </button>
        </form>
        <footer className="mt-6 text-xs text-center text-[#7f8c8d]">
          © DRDO • Confidential • For Authorized Use Only
        </footer>
      </div>
    </div>
  );
};

export default Login;
