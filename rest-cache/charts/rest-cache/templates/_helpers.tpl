{{- define "rest-cache.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" -}}
{{- end -}}

{{- define "rest-cache.fullname" -}}
{{- if .Values.fullnameOverride -}}
{{- .Values.fullnameOverride | trunc 63 | trimSuffix "-" -}}
{{- else -}}
{{- $name := include "rest-cache.name" . -}}
{{- if contains $name .Release.Name -}}
{{- .Release.Name | trunc 63 | trimSuffix "-" -}}
{{- else -}}
{{- printf "%s-%s" .Release.Name $name | trunc 63 | trimSuffix "-" -}}
{{- end -}}
{{- end -}}
{{- end -}}

{{- define "rest-cache.chart" -}}
{{- printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" -}}
{{- end -}}

{{- define "rest-cache.labels" -}}
helm.sh/chart: {{ include "rest-cache.chart" . }}
app.kubernetes.io/name: {{ include "rest-cache.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- end -}}

{{- define "rest-cache.varnishSelectorLabels" -}}
app.kubernetes.io/name: {{ include "rest-cache.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
app.kubernetes.io/component: varnish
{{- end -}}

{{- define "rest-cache.backendHost" -}}
{{- required "varnish.backend.host is required" .Values.varnish.backend.host -}}
{{- end -}}

{{- define "rest-cache.image" -}}
{{- printf "%s:%s" .Values.varnish.image.repository (.Values.varnish.image.tag | default .Chart.AppVersion) -}}
{{- end -}}
