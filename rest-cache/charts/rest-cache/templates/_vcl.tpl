{{- define "rest-cache.defaultVcl" -}}
vcl 4.1;

import std;

backend default {
  .host = "{{ include "rest-cache.backendHost" . }}";
  .port = "{{ .Values.varnish.backend.port }}";
  .connect_timeout = {{ .Values.varnish.backend.connectTimeout }};
  .first_byte_timeout = {{ .Values.varnish.backend.firstByteTimeout }};
  .between_bytes_timeout = {{ .Values.varnish.backend.betweenBytesTimeout }};
}

sub vcl_recv {
  set req.url = std.querysort(req.url);

  if (req.method == "POST" || req.method == "PUT" || req.method == "PATCH" || req.method == "DELETE") {
    call classify_rest_path;
    call invalidate_for_mutation;
    return (pass);
  }

  if (req.method != "GET") {
    return (pass);
  }

  if (req.url !~ "^{{ .Values.apiPrefix }}/") {
    return (pass);
  }

  call classify_rest_path;

  if (!req.http.X-Cache-Collection-Key) {
    return (pass);
  }

  return (hash);
}

sub classify_rest_path {
  unset req.http.X-Cache-Family;
  unset req.http.X-Cache-Resource-ID;
  unset req.http.X-Cache-Resource-Key;
  unset req.http.X-Cache-Collection-Key;

  if (req.url ~ "^{{ .Values.apiPrefix }}/([A-Za-z0-9._~-]+)([/?]|$)") {
    set req.http.X-Cache-Family = regsub(req.url, "^{{ .Values.apiPrefix }}/([A-Za-z0-9._~-]+).*$", "\1");
    set req.http.X-Cache-Collection-Key = "collection:" + req.http.X-Cache-Family;
  }

  if (req.url ~ "^{{ .Values.apiPrefix }}/[A-Za-z0-9._~-]+/([A-Za-z0-9._~-]+)([/?]|$)") {
    set req.http.X-Cache-Resource-ID = regsub(req.url, "^{{ .Values.apiPrefix }}/[A-Za-z0-9._~-]+/([A-Za-z0-9._~-]+).*$", "\1");

    if (req.http.X-Cache-Resource-ID != "search") {
      set req.http.X-Cache-Resource-Key =
        "resource:" + req.http.X-Cache-Family + ":" + req.http.X-Cache-Resource-ID;
    }
  }
}

sub invalidate_for_mutation {
  if (req.method == "POST" && req.http.X-Cache-Collection-Key) {
    ban("obj.http.X-Cache-Collection-Key == " + req.http.X-Cache-Collection-Key);
  }

  if ((req.method == "PUT" || req.method == "PATCH" || req.method == "DELETE") && req.http.X-Cache-Resource-Key) {
    ban("obj.http.X-Cache-Resource-Key == " + req.http.X-Cache-Resource-Key);
    ban("obj.http.X-Cache-Collection-Key == " + req.http.X-Cache-Collection-Key);
  } else if ((req.method == "PUT" || req.method == "PATCH" || req.method == "DELETE") && req.http.X-Cache-Collection-Key) {
    ban("obj.http.X-Cache-Collection-Key == " + req.http.X-Cache-Collection-Key);
  }

{{- range .Values.varnish.dependencyBans }}
  if (req.http.X-Cache-Family == "{{ .family }}") {
{{- range .collectionKeys }}
    ban("obj.http.X-Cache-Collection-Key == {{ . }}");
{{- end }}
  }

{{- end }}
}

sub vcl_hash {
  hash_data(req.method);
  hash_data(req.http.host);
  hash_data(req.url);
}

sub vcl_backend_response {
  if (bereq.method != "GET") {
    set beresp.uncacheable = true;
    return (deliver);
  }

  if (beresp.status < 200 || beresp.status >= 300) {
    set beresp.uncacheable = true;
    return (deliver);
  }

  if (beresp.http.Set-Cookie) {
    set beresp.uncacheable = true;
    return (deliver);
  }

  if (bereq.http.X-Cache-Resource-Key) {
    set beresp.http.X-Cache-Resource-Key = bereq.http.X-Cache-Resource-Key;
  }
  if (bereq.http.X-Cache-Collection-Key) {
    set beresp.http.X-Cache-Collection-Key = bereq.http.X-Cache-Collection-Key;
  }

  set beresp.ttl = {{ .Values.varnish.ttl }};
  set beresp.grace = {{ .Values.varnish.grace }};
  return (deliver);
}

sub vcl_deliver {
  unset resp.http.X-Cache-Resource-Key;
  unset resp.http.X-Cache-Collection-Key;
  if (obj.hits > 0) {
    set resp.http.X-Cache = "HIT";
  } else {
    set resp.http.X-Cache = "MISS";
  }
}
{{- end -}}
