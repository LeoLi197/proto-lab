// frontend/auth.js
// flashmvp认证逻辑 - 简单的前端认证（适合演示，非生产环境）

const AUTH_KEY = 'proto-lab_auth_token'; // Renamed from flashmvp for consistency

// 登录处理
if (document.getElementById('loginForm')) {
    document.getElementById('loginForm').addEventListener('submit', (e) => {
        e.preventDefault();
        const username = document.getElementById('username').value;
        const password = document.getElementById('password').value;
        
        // USERS is defined in config.js
        const user = USERS.find(u => u.username === username && u.password === password);
        if (user) {
            // 生成简单token
            const token = btoa(`${username}:${Date.now()}`);
            localStorage.setItem(AUTH_KEY, token);
            window.location.href = '/dashboard.html';
        } else {
            document.getElementById('error').style.display = 'block';
        }
    });
}

// 检查认证
function checkAuth() {
    const token = localStorage.getItem(AUTH_KEY);
    if (!token) {
        // If not on the login page, redirect to it
        if (window.location.pathname !== '/' && window.location.pathname !== '/index.html') {
             window.location.href = '/index.html';
        }
        return false;
    }
    
    // 简单的过期检查（24小时）
    try {
        const [username, timestamp] = atob(token).split(':');
        if (Date.now() - parseInt(timestamp) > 24 * 60 * 60 * 1000) {
            logout();
            return false;
        }
    } catch (e) {
        logout();
        return false;
    }
    
    return true;
}

// 登出
function logout() {
    localStorage.removeItem(AUTH_KEY);
    window.location.href = '/index.html';
}