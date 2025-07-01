import unittest
from epub_translator.epub import translate_html


class TestAddFunction(unittest.TestCase):

  def test_string_logic(self):
    target = translate_html(
      translate=lambda texts, _: [t for t in texts],
      file_content = "<html><body>hello<span>the</span>world</body></html>",
      report_progress=lambda _: None,
    )
    self.assertEqual(
      first=target,
      second="<html><body>hello<span>the</span>world</body><body>hellotheworld</body></html>",
    )

  def test_pick_and_replace_content(self):
    # Just a smoke test
    translate_html(
      translate=lambda texts, _: [""],
      file_content = self._get_test_xml_content(),
      report_progress=lambda _: None,
    )

  def _get_test_xml_content(self) -> str:
    return """
      <html xmlns="http://www.w3.org/1999/xhtml">\n

      <head>\n <title>The little prince</title>\n
          <meta content="http://www.w3.org/1999/xhtml; charset=utf-8" http-equiv="Content-Type">
          <link href="stylesheet.css" type="text/css" rel="stylesheet"/>
          <style type="text/css">
              \n\t\t@page {
                  margin-bottom: 5.000000pt;
                  margin-top: 5.000000pt;
              }
          </style>
      </head>\n

      <body class="body">\n\n<div class="bs" id="7359">\n<span><br class="calibre3"></span>
              <p class="calibre1"></p>
          </div>\n\n<div class="bs1" id="7360">\n<span> </span></div>\n\n<div class="bs1" id="7361">\n<span> </span></div>\n\n
          <div class="bs6" id="7362">\n<span>Chapter II</span></div>\n\n<div class="bs" id="7363">\n<span><span class="ts3">
                  </span></span></div>\n\n<div class="bs1" id="7364">\n<p class="calibre1"></p>
          </div>\n\n<div class="bs" id="7365">\n<span><span class="ts3"> </span></span></div>\n\n<div class="bs1" id="7366">\n
              <p class="calibre1"></p>
          </div>\n\n
          <div class="bs" id="7367">\n<span><span class="ts3">So I lived my life alone, without anyone that I could
                      really talk to, until I had an accident with my plane in the Desert of Sahara, six years ago. Something
                      was broken in my engine. And as I had with me neither a mechanic nor any passengers, I set myself to
                      attempt the difficult repairs all alone. It was a question of life or death for me: I had scarcely
                      enough drinking water to last a week. The first night, then, I went to sleep on the sand, a thousand
                      miles from any human habitation. I was more isolated than a shipwrecked sailor on a raft in the middle
                      of the ocean. Thus you can imagine my amazement, at sunrise, when I was awakened by an odd little voice.
                      It said:</span></span></div>\n Great \n<div class="bs1" id="7368"> Great\n<p class="calibre1"></p>
          <div>Foobar<span>F</span> SSS <span>A</span></div>
          </div>\n\n<div class="bs" id="7369">\n<span><span class="ts3"> </span></span></div>\n\n<div class="bs1" id="7370">\n
              <p class="calibre1"></p>
          </div>\n\n<div class="bs" id="7371">\n<span><span class="ts3">"If you please-- draw me a sheep!"</span></span></div>
          \n\n<div class="bs1" id="7372">\n<p class="calibre1"></p>
          </div>\n\n<div class="bs" id="7373">\n<span><span class="ts3"> </span></span></div>\n\n<div class="bs1" id="7374">\n
              <p class="calibre1"></p>
          </div>\n\n<div class="bs" id="7375">\n<span><span class="ts3">"What!"</span></span></div>\n\n<div class="bs1"
              id="7376">\n<p class="calibre1"></p>
          </div>\n\n<div class="bs" id="7377">\n<span><span class="ts3"> </span></span></div>\n\n<div class="bs1" id="7378">\n
              <p class="calibre1"></p>
          </div>\n\n<div class="bs" id="7379">\n<span><span class="ts3">"Draw me a sheep!"</span></span></div>\n\n<div
              class="bs1" id="7380">\n<p class="calibre1"></p>
          </div>\n\n<div class="bs" id="7381">\n<span><span class="ts3"> </span></span></div>\n\n<div class="bs1" id="7382">\n
              <p class="calibre1"></p>
          </div>\n\n<div class="bs" id="7383">\n<span><span class="ts3">I jumped to my feet, completely thunderstruck. I
                      blinked my eyes hard. I looked carefully all around me. And I saw a most extraordinary small person, who
                      stood there examining me with great seriousness. Here you may see the best portrait that, later, I was
                      able to make of him. But my drawing is certainly very much less charming than its model.</span></span>
          </div>\n\n<div class="bs1" id="7384">\n<p class="calibre1"></p>
          </div>\n\n<div class="bs" id="7385">\n<span><span class="ts3"> </span></span></div>\n\n<div class="bs1" id="7386">\n
              <p class="calibre1"></p>
          </div>\n\n<div class="bs7" id="7387">\n<p class="calibre1"><span><img src="10807.jpeg" class="calibre8" /></span></p>
          </div>\n\n<div class="bs1" id="7388">\n<p class="calibre1"></p>
          </div>\n\n<div class="bs" id="7389">\n<span><span class="ts3"> </span></span></div>\n\n<div class="bs1" id="7390">\n
              <p class="calibre1"></p>
          </div>\n\n<div class="bs" id="7391">\n<span><span class="ts3">That, however, is not my fault. The grown-ups
                      discouraged me in my painter\'s career when I was six years old, and I never learned to draw anything,
                      except boas from the outside and boas from the inside.</span></span></div>\n\n<div class="bs1"
              id="7392">\n<p class="calibre1"></p>
          </div>\n\n<div class="bs" id="7393">\n<span><span class="ts3"> </span></span></div>\n\n<div class="bs1" id="7394">\n
              <p class="calibre1"></p>
          </div>\n\n<div class="bs" id="7395">\n<span><span class="ts3">Now I stared at this sudden apparition with my eyes
                      fairly starting out of my head in astonishment. Remember, I had crashed in the desert a thousand miles
                      from any inhabited region. And yet my little man seemed neither to be straying uncertainly among the
                      sands, nor to be fainting from fatigue or hunger or thirst or fear. Nothing about him gave any
                      suggestion of a child lost in the middle of the desert, a thousand miles from any human habitation. When
                      at last I was able to speak, I said to him:</span></span></div>\n\n<div class="bs1" id="7396">\n<p
                  class="calibre1"></p>
          </div>\n\n<div class="bs" id="7397">\n<span><span class="ts3"> </span></span></div>\n\n<div class="bs1" id="7398">\n
              <p class="calibre1"></p>
          </div>\n\n<div class="bs" id="7399">\n<span><span class="ts3">"But-- what are you doing here?"</span></span></div>
          \n\n<div class="bs1" id="7400">\n<p class="calibre1"></p>
          </div>\n\n<div class="bs" id="7401">\n<span><span class="ts3"> </span></span></div>\n\n<div class="bs1" id="7402">\n
              <p class="calibre1"></p>
          </div>\n\n<div class="bs" id="7403">\n<span><span class="ts3">And in answer he repeated, very slowly, as if he were
                      speaking of a matter of great consequence:</span></span></div>\n\n<div class="bs1" id="7404">\n<p
                  class="calibre1"></p>
          </div>\n\n<div class="bs" id="7405">\n<span><span class="ts3"> </span></span></div>\n\n<div class="bs1" id="7406">\n
              <p class="calibre1"></p>
          </div>\n\n<div class="bs" id="7407">\n<span><span class="ts3">"If you please-- draw me a sheep..."</span></span>
          </div>\n\n<div class="bs1" id="7408">\n<p class="calibre1"></p>
          </div>\n\n<div class="bs" id="7409">\n<span><span class="ts3"> </span></span></div>\n\n<div class="bs1" id="7410">\n
              <p class="calibre1"></p>
          </div>\n\n<div class="bs" id="7411">\n<span><span class="ts3">When a mystery is too overpowering, one dare not
                      disobey. Absurd as it might seem to me, a thousand miles from any human habitation and in danger of
                      death, I took out of my pocket a sheet of paper and my fountain pen. But then I remembered how my
                      studies had been concentrated on geography, history, arithmetic, and grammar, and I told the little chap
                      (a little crossly, too) that I did not know how to draw. He answered me:</span></span></div>\n\n<div
              class="bs1" id="7412">\n<p class="calibre1"></p>
          </div>\n\n<div class="bs" id="7413">\n<span><span class="ts3"> </span></span></div>\n\n<div class="bs1" id="7414">\n
              <p class="calibre1"></p>
          </div>\n\n<div class="bs" id="7415">\n<span><span class="ts3">"That doesn\'t matter. Draw me a
                      sheep..."</span></span></div>\n\n<div class="bs1" id="7416">\n<p class="calibre1"></p>
          </div>\n\n<div class="bs" id="7417">\n<span><span class="ts3"> </span></span></div>\n\n<div class="bs1" id="7418">\n
              <p class="calibre1"></p>
          </div>\n\n<div class="bs" id="7419">\n<span><span class="ts3">But I had never drawn a sheep. So I drew for him one
                      of the two pictures I had drawn so often. It was that of the boa constrictor from the outside. And I was
                      astounded to hear the little fellow greet it with,</span></span></div>\n\n<div class="bs1" id="7420">\n
              <p class="calibre1"></p>
          </div>\n\n<div class="bs" id="7421">\n<span><span class="ts3"> </span></span></div>\n\n<div class="bs1" id="7422">\n
              <p class="calibre1"></p>
          </div>\n\n<div class="bs" id="7423">\n<span><span class="ts3">"No, no, no! I do not want an elephant inside a boa
                      constrictor. A boa constrictor is a very dangerous creature, and an elephant is very cumbersome. Where I
                      live, everything is very small. What I need is a sheep. Draw me a sheep."</span></span></div>\n\n<div
              class="bs1" id="7424">\n<p class="calibre1"></p>
          </div>\n\n<div class="bs" id="7425">\n<span><span class="ts3"> </span></span></div>\n\n<div class="bs1" id="7426">\n
              <p class="calibre1"></p>
          </div>\n\n<div class="bs" id="7427">\n<span><span class="ts3">So then I made a drawing.</span></span></div>\n\n<div
              class="bs1" id="7428">\n<p class="calibre1"></p>
          </div>\n\n<div class="bs" id="7429">\n<span><span class="ts3"> </span></span></div>\n\n<div class="bs1" id="7430">\n
              <p class="calibre1"></p>
          </div>\n\n<div class="bs7" id="7431">\n<p class="calibre1"><span><img src="10808.jpeg" class="calibre9" /></span></p>
          </div>\n\n<div class="bs1" id="7432">\n<p class="calibre1"></p>
          </div>\n\n<div class="bs" id="7433">\n<span><span class="ts3"> </span></span></div>\n\n<div class="bs1" id="7434">\n
              <p class="calibre1"></p>
          </div>\n\n<div class="bs" id="7435">\n<span><span class="ts3">He looked at it carefully, then he said:</span></span>
          </div>\n\n<div class="bs1" id="7436">\n<p class="calibre1"></p>
          </div>\n\n<div class="bs" id="7437">\n<span><span class="ts3"> </span></span></div>\n\n<div class="bs1" id="7438">\n
              <p class="calibre1"></p>
          </div>\n\n<div class="bs" id="7439">\n<span><span class="ts3">"No. This sheep is already very sickly. Make me
                      another."</span></span></div>\n\n<div class="bs1" id="7440">\n<p class="calibre1"></p>
          </div>\n\n<div class="bs" id="7441">\n<span><span class="ts3"> </span></span></div>\n\n<div class="bs1" id="7442">\n
              <p class="calibre1"></p>
          </div>\n\n<div class="bs" id="7443">\n<span><span class="ts3">So I made another drawing.</span></span></div>\n\n<div
              class="bs1" id="7444">\n<p class="calibre1"></p>
          </div>\n\n<div class="bs" id="7445">\n<span><span class="ts3"> </span></span></div>\n\n<div class="bs1" id="7446">\n
              <p class="calibre1"></p>
          </div>\n\n<div class="bs7" id="7447">\n<p class="calibre1"><span><img src="10809.jpeg" class="calibre10" /></span></p>
          </div>\n\n<div class="bs1" id="7448">\n<p class="calibre1"></p>
          </div>\n\n<div class="bs" id="7449">\n<span><span class="ts3"> </span></span></div>\n\n<div class="bs1" id="7450">\n
              <p class="calibre1"></p>
          </div>\n\n<div class="bs" id="7451">\n<span><span class="ts3">My friend smiled gently and indulgently.</span></span>
          </div>\n\n<div class="bs1" id="7452">\n<p class="calibre1"></p>
          </div>\n\n<div class="bs" id="7453">\n<span><span class="ts3"> </span></span></div>\n\n<div class="bs1" id="7454">\n
              <p class="calibre1"></p>
          </div>\n\n<div class="bs" id="7455">\n<span><span class="ts3">"You see yourself," he said, "that this is not a
                      sheep. This is a ram. It has horns."</span></span></div>\n\n<div class="bs1" id="7456">\n<p
                  class="calibre1"></p>
          </div>\n\n<div class="bs" id="7457">\n<span><span class="ts3"> </span></span></div>\n\n<div class="bs1" id="7458">\n
              <p class="calibre1"></p>
          </div>\n\n<div class="bs" id="7459">\n<span><span class="ts3">So then I did my drawing over once more.</span></span>
          </div>\n\n<div class="bs1" id="7460">\n<p class="calibre1"></p>
          </div>\n\n<div class="bs" id="7461">\n<span><span class="ts3"> </span></span></div>\n\n<div class="bs1" id="7462">\n
              <p class="calibre1"></p>
          </div>\n\n<div class="bs7" id="7463">\n<p class="calibre1"><span><img src="10810.jpeg" class="calibre11" /></span></p>
          </div>\n\n<div class="bs1" id="7464">\n<p class="calibre1"></p>
          </div>\n\n<div class="bs" id="7465">\n<span><span class="ts3"> </span></span></div>\n\n<div class="bs1" id="7466">\n
              <p class="calibre1"></p>
          </div>\n\n<div class="bs" id="7467">\n<span><span class="ts3">But it was rejected too, just like the
                      others.</span></span></div>\n\n<div class="bs1" id="7468">\n<p class="calibre1"></p>
          </div>\n\n<div class="bs" id="7469">\n<span><span class="ts3"> </span></span></div>\n\n<div class="bs1" id="7470">\n
              <p class="calibre1"></p>
          </div>\n\n<div class="bs" id="7471">\n<span><span class="ts3">"This one is too old. I want a sheep that will live a
                      long time."</span></span></div>\n\n<div class="bs1" id="7472">\n<p class="calibre1"></p>
          </div>\n\n<div class="bs" id="7473">\n<span><span class="ts3"> </span></span></div>\n\n<div class="bs1" id="7474">\n
              <p class="calibre1"></p>
          </div>\n\n<div class="bs" id="7475">\n<span><span class="ts3">By this time my patience was exhausted, because I was
                      in a hurry to start taking my engine apart.</span></span></div>\n\n<div class="bs1" id="7476">\n<p
                  class="calibre1"></p>
          </div>\n\n<div class="bs" id="7477">\n<span><span class="ts3"> </span></span></div>\n\n<div class="bs1" id="7478">\n
              <p class="calibre1"></p>
          </div>\n\n<div class="bs" id="7479">\n<span><span class="ts3">So I tossed off this drawing. And I threw out an
                      explanation with it.</span></span></div>\n\n<div class="bs1" id="7480">\n<p class="calibre1"></p>
          </div>\n\n<div class="bs" id="7481">\n<span><span class="ts3"> </span></span></div>\n\n<div class="bs1" id="7482">\n
              <p class="calibre1"></p>
          </div>\n\n<div class="bs7" id="7483">\n<p class="calibre1"><span><img src="10811.jpeg" class="calibre12" /></span></p>
          </div>\n\n<div class="bs1" id="7484">\n<p class="calibre1"></p>
          </div>\n\n<div class="bs" id="7485">\n<span><span class="ts3"> </span></span></div>\n\n<div class="bs1" id="7486">\n
              <p class="calibre1"></p>
          </div>\n\n<div class="bs" id="7487">\n<span><span class="ts3">"This is only his box. The sheep you asked for is
                      inside."</span></span></div>\n\n<div class="bs1" id="7488">\n<p class="calibre1"></p>
          </div>\n\n<div class="bs" id="7489">\n<span><span class="ts3"> </span></span></div>\n\n<div class="bs1" id="7490">\n
              <p class="calibre1"></p>
          </div>\n\n<div class="bs" id="7491">\n<span><span class="ts3">I was very surprised to see a light break over the
                      face of my young judge:</span></span></div>\n\n<div class="bs1" id="7492">\n<p class="calibre1"></p>
          </div>\n\n<div class="bs" id="7493">\n<span><span class="ts3"> </span></span></div>\n\n<div class="bs1" id="7494">\n
              <p class="calibre1"></p>
          </div>\n\n<div class="bs" id="7495">\n<span><span class="ts3">"That is exactly the way I wanted it! Do you think
                      that this sheep will have to have a great deal of grass?"</span></span></div>\n\n<div class="bs1"
              id="7496">\n<p class="calibre1"></p>
          </div>\n\n<div class="bs" id="7497">\n<span><span class="ts3"> </span></span></div>\n\n<div class="bs1" id="7498">\n
              <p class="calibre1"></p>
          </div>\n\n<div class="bs" id="7499">\n<span><span class="ts3">"Why?"</span></span></div>\n\n<div class="bs1"
              id="7500">\n<p class="calibre1"></p>
          </div>\n\n<div class="bs" id="7501">\n<span><span class="ts3"> </span></span></div>\n\n<div class="bs1" id="7502">\n
              <p class="calibre1"></p>
          </div>\n\n<div class="bs" id="7503">\n<span><span class="ts3">"Because where I live everything is very
                      small..."</span></span></div>\n\n<div class="bs1" id="7504">\n<p class="calibre1"></p>
          </div>\n\n<div class="bs" id="7505">\n<span><span class="ts3"> </span></span></div>\n\n<div class="bs1" id="7506">\n
              <p class="calibre1"></p>
          </div>\n\n<div class="bs" id="7507">\n<span><span class="ts3">"There will surely be enough grass for him," I said.
                      "It is a very small sheep that I have given you."</span></span></div>\n\n<div class="bs1" id="7508">\n<p
                  class="calibre1"></p>
          </div>\n\n<div class="bs" id="7509">\n<span><span class="ts3"> </span></span></div>\n\n<div class="bs1" id="7510">\n
              <p class="calibre1"></p>
          </div>\n\n<div class="bs" id="7511">\n<span><span class="ts3">He bent his head over the drawing:</span></span></div>
          \n\n<div class="bs1" id="7512">\n<p class="calibre1"></p>
          </div>\n\n<div class="bs" id="7513">\n<span><span class="ts3"> </span></span></div>\n\n<div class="bs1" id="7514">\n
              <p class="calibre1"></p>
          </div>\n\n<div class="bs" id="7515">\n<span><span class="ts3">"Not so small that-- Look! He has gone to
                      sleep..."</span></span></div>\n\n<div class="bs1" id="7516">\n<p class="calibre1"></p>
          </div>\n\n<div class="bs" id="7517">\n<span><span class="ts3"> </span></span></div>\n\n<div class="bs1" id="7518">\n
              <p class="calibre1"></p>
          </div>\n\n<div class="bs" id="7519">\n<span><span class="ts3">And that is how I made the acquaintance of the little
                      prince.</span></span></div>\n\n<div class="bs1" id="7520">\n<p class="calibre1"></p>
          </div>\n\n
      </body>\n

      </html>
      """