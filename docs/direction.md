# パラメータの direction の処理

doxybook2 では direction を解釈できないので、

```xml
<parametername>a</parametername>
<parametername direction="in">b</parametername>
<parametername direction="out">c</parametername>
<parametername direction="in, out">d</parametername>
```

に対して

```xml
<parametername>b</parametername>
<parametername>[in] b</parametername>
<parametername>[out] c</parametername>
<parametername>[in, out] d</parametername>
```

になるように前処理を行う。
