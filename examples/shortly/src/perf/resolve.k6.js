import http from "k6/http";
export const options = { thresholds: { http_req_duration: ["p(99)<50"] } };
export default function () { http.get("http://localhost:8080/abc1234", { redirects: 0 }); }
