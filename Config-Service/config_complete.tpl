<h1>Agency Dashboard Configuration</h1>
<span style="text-align: center;">
%if defined(error)
<p style="color: red;">There was an error retrieving the Adwords authorization.</p>
<p>{{error}}</p>
<p style="color: red;">Please check your setup and try again.</p>
%else
<p style="color: greenyellow;">Congratulations!</p>
<p>The Agency Dashboard backend should now have access to your Ads data.</p>
%end
</span>
