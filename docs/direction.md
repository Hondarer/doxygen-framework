# パラメーターの direction の処理

Doxybook2 では direction を解釈できないため、

```xml
<parametername>a</parametername>
<parametername direction="in">b</parametername>
<parametername direction="out">c</parametername>
<parametername direction="in, out">d</parametername>
```

に対して

```xml
<parametername>a</parametername>
<parametername>[in] b</parametername>
<parametername>[out] c</parametername>
<parametername>[in, out] d</parametername>
```

となるように前処理を実行します。
