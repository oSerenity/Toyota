
function GetModelName() {
  return "CAMRY";
}
function GetModelCodes() {
  const XmlFile = "model.xml"; // Path to the XML file
  const HomePath = "./";

  fetch(HomePath + XmlFile)
    .then(response => response.text())
    .then(xmlString => {
      const parser = new DOMParser();
      const xmldoc = parser.parseFromString(xmlString, "application/xml");
      const Root = xmldoc.documentElement; // Get the root node
      let sRet = "";
      const Len = Root.childNodes.length; // Number of child nodes

      for (let i = 0; i < Len; i++) {
        if (Root.childNodes[i].nodeName === "modelcode") {
          const oChildNode = Root.childNodes.item(i); // Move to the current child node (menu)
          const ModelLen = oChildNode.childNodes.length;

          for (let j = 0; j < ModelLen; j++) {
            if (sRet !== "") sRet += "<br>";
            sRet += oChildNode.childNodes[j].textContent;
          }
        }
      }
      document.body.innerHTML = sRet;
    })
    .catch(error => {
      console.error('Error loading the XML file:', error);
    });
}

function GetTitleName() 
{
    return "CAMRY";
  
}
function GetCopyrightYear() {
    return "2003-2004";
}