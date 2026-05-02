import { FormEvent, useEffect, useState } from "react";

const API_URL = window.location.hostname === "localhost" || window.location.hostname === "127.0.0.1" 
  ? "http://127.0.0.1:8000" 
  : "/api"; // On Vercel, API routes are prefixed with /api via vercel.json rewrites
const TOKEN_KEY = "todo_auth_token";

type View = "login" | "register" | "protected";

type User = {
  id: number;
  username: string;
  email: string | null;
};

type Todo = {
  id: number;
  user_id: number;
  title: string;
  completed: boolean;
  due_date: string | null;
};

type TokenResponse = {
  access_token: string;
  token_type: "bearer";
};

type ProtectedResponse = {
  message: string;
  user: User;
};

type ApiError = {
  detail?: string | Array<{ msg?: string }>;
};

type ApiOptions = {
  body?: unknown;
  method?: "GET" | "POST" | "PUT" | "DELETE";
  token?: string;
};

type AuthForm = {
  username: string;
  password: string;
  email: string;
};

const emptyForm: AuthForm = {
  username: "",
  password: "",
  email: ""
};

async function readError(response: Response): Promise<string> {
  try {
    const data = (await response.json()) as ApiError;
    if (typeof data.detail === "string") {
      return data.detail;
    }

    if (Array.isArray(data.detail)) {
      return data.detail.map((item) => item.msg).filter(Boolean).join(", ") || "Invalid request";
    }

    return "Something went wrong";
  } catch {
    return "Something went wrong";
  }
}

async function apiRequest<TResponse>(path: string, options: ApiOptions = {}): Promise<TResponse> {
  const headers = new Headers();

  if (options.body !== undefined) {
    headers.set("Content-Type", "application/json");
  }

  if (options.token) {
    headers.set("Authorization", `Bearer ${options.token}`);
  }

  let response: Response;

  try {
    response = await fetch(`${API_URL}${path}`, {
      method: options.method ?? "GET",
      headers,
      body: options.body === undefined ? undefined : JSON.stringify(options.body)
    });
  } catch {
    throw new Error("Cannot reach the backend. Make sure FastAPI is running on http://127.0.0.1:8000.");
  }

  if (!response.ok) {
    throw new Error(await readError(response));
  }

  return (await response.json()) as TResponse;
}

function getTodoTimeClass(todo: Todo) {
  if (todo.completed || !todo.due_date) return "";
  const now = new Date();
  const dueDate = new Date(todo.due_date);
  const diffMs = dueDate.getTime() - now.getTime();
  
  if (diffMs < 0) return "overdue";
  if (diffMs < 24 * 60 * 60 * 1000) return "due-soon";
  return "";
}

function formatDueDate(dateStr: string) {
  return new Date(dateStr).toLocaleString(undefined, { 
    month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit'
  });
}

function App() {
  const [view, setView] = useState<View>("login");
  const [token, setToken] = useState<string>(() => localStorage.getItem(TOKEN_KEY) ?? "");
  const [form, setForm] = useState<AuthForm>(emptyForm);
  const [user, setUser] = useState<User | null>(null);
  const [statusMessage, setStatusMessage] = useState<string>("");
  const [error, setError] = useState<string>("");
  const [isSubmitting, setIsSubmitting] = useState<boolean>(false);
  const [isVerifying, setIsVerifying] = useState<boolean>(false);

  const [todos, setTodos] = useState<Todo[]>([]);
  const [newTodoTitle, setNewTodoTitle] = useState("");
  const [newTodoDueDate, setNewTodoDueDate] = useState("");
  const [isFetchingTodos, setIsFetchingTodos] = useState(false);
  const [activeAlerts, setActiveAlerts] = useState<string[]>([]);
  const alertedIds = useState(() => new Set<number>())[0]; // Persistent set for alerted IDs

  useEffect(() => {
    if (!token) {
      setView("login");
      setUser(null);
      return;
    }

    let isMounted = true;

    async function verifyToken() {
      setIsVerifying(true);
      setError("");

      try {
        const data = await apiRequest<ProtectedResponse>("/protected", { token });
        if (isMounted) {
          setUser(data.user);
          setStatusMessage(data.message);
          setView("protected");
        }
      } catch (caughtError) {
        if (isMounted) {
          const message = caughtError instanceof Error ? caughtError.message : "Session expired";
          localStorage.removeItem(TOKEN_KEY);
          setToken("");
          setUser(null);
          setError(message);
          setView("login");
        }
      } finally {
        if (isMounted) {
          setIsVerifying(false);
        }
      }
    }

    void verifyToken();

    return () => {
      isMounted = false;
    };
  }, [token]);

  useEffect(() => {
    if (view === "protected" && token) {
      void fetchTodos();
    }
  }, [view, token]);

  useEffect(() => {
    if (view !== "protected" || todos.length === 0) return;

    const interval = setInterval(() => {
      const now = new Date();
      const newAlerts: string[] = [];
      
      todos.forEach(todo => {
        if (!todo.completed && todo.due_date) {
          const dueDate = new Date(todo.due_date);
          const timeDiff = now.getTime() - dueDate.getTime();
          
          // Alert if it's due now or became due in the last 30 seconds, 
          // and we haven't alerted for it yet.
          if (timeDiff >= 0 && timeDiff <= 30000 && !alertedIds.has(todo.id)) {
            newAlerts.push(`Task due now: ${todo.title}`);
            alertedIds.add(todo.id);
          }
        }
      });
      
      if (newAlerts.length > 0) {
        setActiveAlerts(prev => [...prev, ...newAlerts]);
        setTimeout(() => {
          setActiveAlerts(prev => prev.filter(a => !newAlerts.includes(a)));
        }, 8000);
      }
    }, 5000);
    
    return () => clearInterval(interval);
  }, [todos, view, alertedIds]);

  async function fetchTodos() {
    setIsFetchingTodos(true);
    try {
      const data = await apiRequest<Todo[]>("/todos", { token });
      setTodos(data);
    } catch (caughtError) {
      setError("Failed to load todos");
    } finally {
      setIsFetchingTodos(false);
    }
  }

  async function createTodo(e: FormEvent) {
    e.preventDefault();
    if (!newTodoTitle.trim()) return;
    try {
      const newTodo = await apiRequest<Todo>("/todos", {
        method: "POST",
        token,
        body: { 
          title: newTodoTitle,
          due_date: newTodoDueDate ? new Date(newTodoDueDate).toISOString() : null
        }
      });
      setTodos(prev => [newTodo, ...prev]);
      setNewTodoTitle("");
      setNewTodoDueDate("");
    } catch (err) {
      setError("Failed to create todo");
    }
  }

  async function toggleTodo(todo: Todo) {
    // Optimistic update
    setTodos(prev => prev.map(t => t.id === todo.id ? { ...t, completed: !t.completed } : t));
    
    try {
      const updated = await apiRequest<Todo>(`/todos/${todo.id}`, {
        method: "PUT",
        token,
        body: { completed: !todo.completed }
      });
      // Sync with server response
      setTodos(prev => prev.map(t => t.id === todo.id ? updated : t));
    } catch (err) {
      setError("Failed to update todo");
      void fetchTodos(); // Re-sync on error
    }
  }

  async function deleteTodo(id: number) {
    // Optimistic removal
    setTodos(prev => prev.filter(t => t.id !== id));
    
    try {
      await apiRequest(`/todos/${id}`, {
        method: "DELETE",
        token
      });
    } catch (err) {
      setError("Failed to delete todo");
      void fetchTodos(); // Re-sync on error
    }
  }

  function updateField(field: keyof AuthForm, value: string) {
    setForm((currentForm) => ({ ...currentForm, [field]: value }));
  }

  function resetAuthState(nextView: View) {
    setView(nextView);
    setForm(emptyForm);
    setError("");
    setStatusMessage("");
  }

  async function register(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setIsSubmitting(true);
    setError("");
    setStatusMessage("");

    try {
      await apiRequest<User>("/register", {
        method: "POST",
        body: {
          username: form.username,
          password: form.password,
          email: form.email || null
        }
      });

      setStatusMessage("Account created. You can log in now.");
      setView("login");
      setForm({ ...emptyForm, username: form.username });
    } catch (caughtError) {
      const message = caughtError instanceof Error ? caughtError.message : "Registration failed";
      setError(message);
    } finally {
      setIsSubmitting(false);
    }
  }

  async function login(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setIsSubmitting(true);
    setError("");
    setStatusMessage("");

    try {
      const data = await apiRequest<TokenResponse>("/login", {
        method: "POST",
        body: {
          username: form.username,
          password: form.password
        }
      });
      localStorage.setItem(TOKEN_KEY, data.access_token);
      setToken(data.access_token);
      setForm(emptyForm);
    } catch (caughtError) {
      const message = caughtError instanceof Error ? caughtError.message : "Invalid credentials";
      setError(message);
    } finally {
      setIsSubmitting(false);
    }
  }

  function logout() {
    localStorage.removeItem(TOKEN_KEY);
    setToken("");
    setUser(null);
    setStatusMessage("");
    setError("");
    setView("login");
  }

  const isLogin = view === "login";
  const pageTitle = isLogin ? "Log in" : "Create account";

  if (isVerifying) {
    return (
      <main className="page">
        <section className="panel center-panel">
          <div className="spinner" aria-label="Loading" />
          <p>Checking your session...</p>
        </section>
      </main>
    );
  }

  if (view === "protected" && user) {
    return (
      <main className="page">
        <section className="panel dashboard">
          <div>
            <p className="eyebrow">To-Do List</p>
            <h1>Welcome, {user.username}</h1>
            <p className="muted">{statusMessage}</p>
          </div>

          <div className="todo-container">
            <form onSubmit={createTodo} className="todo-form">
              <input
                type="text"
                placeholder="What needs to be done?"
                value={newTodoTitle}
                onChange={(e) => setNewTodoTitle(e.target.value)}
                required
              />
              <input 
                type="datetime-local" 
                value={newTodoDueDate}
                onChange={(e) => setNewTodoDueDate(e.target.value)}
              />
              <button type="submit" className="primary-button">Add</button>
            </form>

            {isFetchingTodos ? (
              <div className="spinner" aria-label="Loading todos" />
            ) : todos.length === 0 ? (
              <p className="muted text-center">No tasks yet. Add one above!</p>
            ) : (
              <ul className="todo-list">
                {todos.map(todo => (
                  <li key={todo.id} className={`todo-item ${todo.completed ? "completed" : ""} ${getTodoTimeClass(todo)}`}>
                    <label className="todo-label">
                      <input
                        type="checkbox"
                        checked={todo.completed}
                        onChange={() => void toggleTodo(todo)}
                      />
                      <div className="todo-details">
                        <span className="todo-title">{todo.title}</span>
                        {todo.due_date && <span className="due-date-badge">{formatDueDate(todo.due_date)}</span>}
                      </div>
                    </label>
                    <button type="button" className="delete-button" onClick={() => void deleteTodo(todo.id)}>
                      &times;
                    </button>
                  </li>
                ))}
              </ul>
            )}
          </div>

          <button className="secondary-button logout-button" type="button" onClick={logout}>
            Logout
          </button>
          
          {activeAlerts.length > 0 && (
            <div className="alert-container">
              {activeAlerts.map((alert, i) => (
                <div key={i} className="toast-alert">
                  🔔 {alert}
                </div>
              ))}
            </div>
          )}
        </section>
      </main>
    );
  }

  return (
    <main className="page">
      <section className="panel auth-panel">
        <div className="auth-header">
          <p className="eyebrow">To-Do App</p>
          <h1>{pageTitle}</h1>
          <p className="muted">
            {isLogin ? "Use your account to continue." : "Create an account to access protected tasks."}
          </p>
        </div>

        {error && <p className="alert error">{error}</p>}
        {statusMessage && <p className="alert success">{statusMessage}</p>}

        <form onSubmit={isLogin ? login : register}>
          <label>
            Username
            <input
              autoComplete="username"
              minLength={3}
              onChange={(event) => updateField("username", event.target.value)}
              required
              type="text"
              value={form.username}
            />
          </label>

          {!isLogin && (
            <label>
              Email
              <input
                autoComplete="email"
                onChange={(event) => updateField("email", event.target.value)}
                type="email"
                value={form.email}
              />
            </label>
          )}

          <label>
            Password
            <input
              autoComplete={isLogin ? "current-password" : "new-password"}
              minLength={8}
              onChange={(event) => updateField("password", event.target.value)}
              required
              type="password"
              value={form.password}
            />
          </label>

          <button disabled={isSubmitting} type="submit">
            {isSubmitting && <span className="button-spinner" />}
            {isSubmitting ? "Please wait..." : pageTitle}
          </button>
        </form>

        <button
          className="link-button"
          type="button"
          onClick={() => resetAuthState(isLogin ? "register" : "login")}
        >
          {isLogin ? "Need an account? Register" : "Already have an account? Log in"}
        </button>
      </section>
    </main>
  );
}

export default App;
