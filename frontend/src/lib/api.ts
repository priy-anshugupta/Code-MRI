import axios from "axios"

const API_BASE = process.env.NEXT_PUBLIC_API_URL?.replace(/\/$/, "") || "http://localhost:8000"

export const api = axios.create({
    baseURL: API_BASE,
    withCredentials: false,
    headers: {
        "Content-Type": "application/json",
    },
})

export const buildApiUrl = (path: string) => {
    if (!path.startsWith("/")) return `${API_BASE}/${path}`
    return `${API_BASE}${path}`
}
