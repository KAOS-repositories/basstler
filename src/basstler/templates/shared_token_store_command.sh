{#- The command storing one shared token as every secret its jobs read
    (SharedToken.store_command): it asks for the token once at a hidden prompt and pipes
    it into one gh secret set per secret, so it never reaches a command line. -#}
bash -c '
read -rsp "token: " token && echo &&
{% for stored in secrets %}
printf %s "$token" | gh secret set {{ stored.secret }} --repo {{ stored.repository.full_name }}{% if not loop.last %} &&{% endif %}

{% endfor %}
'
