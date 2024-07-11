// JavaScript Document
function showmenu_opera(t)
{
		var m = eval(t);
		var mt = eval(t+'_t');
		var mtable = eval(t+'_table');
	if (mtable.style.visibility == 'hidden')
	{	
		mtable.style.visibility = 'visible';
		mtable.style.innerHeight += 50;
		mtable.style.background = "FF0000"
		document.mtable.write = "Hello!"
	}
	else
	{	mtable.style.visibility  = 'hidden';	}
}
function showmenu(t)
{
	if (document.all)
	{
		var m = eval(t);
		if (m.style.display == "none")
		{		m.style.display = "inline";		}
		else
		{		m.style.display = "none";		}
	}
	else
	{
		var para = document.getElementById(t).style.display;
		if (para == "none") 
		{	
			document.getElementById(t).style.display = "inline";	
			document.getElementById(t).style.visibility = "visible";
		}
		else
		{ 
			document.getElementById(t).style.display = "none";	
			document.getElementById(t).style.visibility = "hidden";
			document.getElementById(t).style.display = "inline";	
			document.getElementById(t).style.display = "none";	
		}
	}
}