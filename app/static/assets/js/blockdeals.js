const steem = new dsteem.Client('https://api.steemit.com');
username = "";

function getDiscussions(kind, start_author=false, start_permlink=false) {
  var query={
    tag: 'blockdeals',
    limit: 25
  };
  var start_from = 0;
  if (start_author !== false && start_permlink !== false) {
    query['start_author'] = start_author;
    query['start_permlink'] = start_permlink;
    start_from = 1;
    console.log('pagination', query);
    $('more_button').remove();
  }
  steem.database.getDiscussions(kind, query).then(function(discussions){
    const deal_template = doT.template(`
        <div class="row" style="margin-bottom:0">
          <div class="col s12 m2">
            <div class="row" style="margin-bottom:3px;">
              <div class="col m12 s6 offset-s3 center-align">
                <img class="lazy deal-image responsive-img" data-src="https://steemitimages.com/250x250/{{=it.deal.post_image}}" onerror="this.src='/assets/images/logo_round.png';" />
              </div>
            </div>

            <div class="lazy row grey-text lighten-2" data-loader="votes" data-permlink="{{=it.post.permlink}}" data-author="{{=it.post.author}}" style="margin-bottom:3px;">
              <div class="col s12 center-align voting truncate">
                <span class="upVote"><i class="fas fa-spinner fa-spin fa-fw"></i></span>
                <i onclick="voteup(this)" class="upVoteThumb vote fas fa-thumbs-up fa-fw"></i>
                &bull;
                <i onclick="flag(this)" class="dnVoteThumb vote fas fa-thumbs-down fa-fw"></i>
                <span class="dnVote"><i class="fas fa-spinner fa-spin fa-fw"></i></span>
              </div>
              <div id="visit" class="col s12 center-align supporter">
                <a id="dealdirect" href="{{=it.deal.url}}" class="waves-effect waves-light btn-small blue tooltipped" data-tooltip="Thanks for supporting this deal! Here is your direct link &#128571;" style="margin-top: 6px;">go to deal</a>
              </div>
            </div>
          </div>

          <div class="col s12 m10">
            {{?it.deal.soon}}<span class="new badge red pulse" data-badge-caption="{{=it.deal.soon}}"><i class="fa fa-clock"></i> Expires in</span>{{?}}
            {{?it.deal.freebie}}<a href="/freebies"><span class="new badge green" data-badge-caption="FREEBIE"><i class="fa fa-certificate"></i></span></a>{{?}}
            {{?it.deal.country_code}}<a href="/country/{{=it.deal.country_code}}"><span class="new badge grey lighten-3" title="{{=it.deal.country_code}}" data-badge-caption=""><div class="country-select"><div class="flag {{=it.deal.country_code}}"></div></div></span></a>{{?}}
            <h2>{{?!it.deal.available}}<span class="red white-text expired">&nbsp;<i class="fas fa-exclamation-triangle fa-fw"></i> <b>EXPIRED</b> </span> {{?}}{{?it.deal.coming_soon}}<span class="blue white-text expired">&nbsp;<i class="fas fa-clock fa-fw"></i> <b>in {{=it.deal.date_begins}}</b> </span> {{?}}<span class="{{?!it.deal.available}}unavailable{{?}}"><a href="/blockdeals/@{{=it.post.author}}/{{=it.post.permlink}}">{{=it.deal.title}}</a></span></h2>
            <p style="margin-bottom:0">{{=it.deal.description}}</p>
            <div class="lazy row" data-loader="votes" data-permlink="{{=it.post.permlink}}" data-author="{{=it.post.author}}" style="margin-bottom:3px;">
              <div class="col s8">
                <p class="grey-text lighten-3">
                  <b>Posted by:</b> <a href="https://steemit.com/@{{=it.post.author }}">@{{=it.post.author}}</a>
                  | <span class="comments"><i class="fas fa-spinner fa-spin fa-fw"></i></span> <i class="fas fa-comments fa-fw"></i>
                  | <b>End{{?it.deal.future_end}}s{{??}}ed{{?}}:</b> {{=it.deal.date_ends}}
                </p>
              </div>
              <div class="col s4">
                <p class="right-align">
                  <a class="waves-effect waves-light btn orange darken-2 tooltipped" data-position="top" data-tooltip="<i class='fas fa-thumbs-up'></i> Upvote good deals! and flag spam <i class='fas fa-thumbs-down'></i>" href="/blockdeals/@{{=it.post.author}}/{{=it.post.permlink}}">More details <i class="material-icons right">send</i></a>
                </p>
              </div>
            </div>
          </div>
        </div>
        <div class="row">
          <div class="col s12">
            <hr/>
          </div>
        </div>`);
    for (var post=start_from, len=discussions.length; post < len; post++) {
      console.log("post", post, discussions[post].permlink);
      var json_metadata = JSON.parse(discussions[post].json_metadata);
      if (json_metadata.tags.includes("delete") || (json_metadata.tags.includes("delist"))) { continue; }
      if (json_metadata.hasOwnProperty("deal")) {
        json_metadata.deal['available'] = moment(json_metadata.deal.date_end).endOf('day').isAfter(moment());
        json_metadata.deal['coming_soon'] = moment(json_metadata.deal.date_start).startOf('day').isAfter(moment());
        var deal_time_end = moment.duration(moment(json_metadata.deal.date_end).endOf('day').diff(moment()));
        var deal_time_start = moment.duration(moment(json_metadata.deal.date_start).startOf('day').diff(moment()));
        json_metadata.deal['date_ends'] = deal_time_end.humanize();
        json_metadata.deal['date_begins'] = deal_time_start.humanize();
        json_metadata.deal['future_end'] = deal_time_end > 0;
        if (deal_time_end.asHours() >= 0 && deal_time_end.asHours() < 48) {
          json_metadata.deal['soon'] = deal_time_end.humanize();
        }
        if (json_metadata.deal['available']) {
          json_metadata.deal['date_ends'] = "in " + json_metadata.deal['date_ends'];
        } else {
          json_metadata.deal['date_ends'] = json_metadata.deal['date_ends'] + " ago";
        }
        json_metadata.deal.post_image = json_metadata.image[0];
        json_metadata.deal.description = jQuery.trim(json_metadata.deal.description).substring(0, 250).trim(this);
        json_metadata.deal.description = _.escape(json_metadata.deal.description);
        if (json_metadata.deal.description.length >= 249) {
          json_metadata.deal.description = json_metadata.deal.description + "&hellip;";
        }
        json_metadata.deal.title = _.escape(json_metadata.deal.title);
        json_metadata.deal.image_url = _.escape(json_metadata.deal.image_url);
        json_metadata.deal.url = _.escape(json_metadata.deal.url);
        $('.section').append(deal_template({'deal': json_metadata.deal, 'post': discussions[post], 'last': post+1 == len}));
      }
      if (post == len-1) {
        const more_template = doT.template(`
          <div id="more_button" class="row">
            <div class="col s12 center-align">
              <a id="more_deals" onclick="getDiscussions('{{=it.kind}}','{{=it.author}}','{{=it.permlink}}')" class="waves-effect waves-light btn-small orange darken-2">More Deals</a>
            </div>
          </div>`);
        $('.section').append(more_template({'kind': kind, 'author': discussions[post].author, 'permlink': discussions[post].permlink}));
      }
    }
    // new lazy objects have been added to the dom
    $(".lazy").Lazy({
      votes: function(e) {
        update_votes(e);
      }
    });
    $('.tooltipped').tooltip();
  });
}

function voteup(e) {
  var parent_el = e.parentNode.parentNode; // for closure
  var a = $(parent_el).data("author");
  var p = $(parent_el).data("permlink");
  $(parent_el).find(".upVoteThumb").addClass("fa-spin");
  $.get("/vote/" + a + "/" + p + "/up", function(data) {
    if (data['status']) { M.toast({html: 'Vote accepted'}) }
    else { M.toast({html: 'Vote failed: ' + data['msg']}) }
    update_votes(parent_el);
    // could take 3 seconds for block to be accepted
    setTimeout(update_votes, 3000, parent_el);
    $(parent_el).find(".upVoteThumb").removeClass("fa-spin");
  }).fail(function() {
    M.toast({html: 'Vote failed'});
    update_votes(parent_el);
    $(parent_el).find(".upVoteThumb").removeClass("fa-spin");
  });
}

function flag(e) {
  var parent_el = e.parentNode.parentNode; // for closure
  var a = $(parent_el).data("author");
  var p = $(parent_el).data("permlink");
  $(parent_el).find(".dnVoteThumb").addClass("fa-spin");
  $.get("/vote/" + a + "/" + p + "/flag", function(data) {
    if (data['status']) { M.toast({html: 'Flagged'}) }
    else { M.toast({html: 'Flag failed: ' + data['msg']}) }
    update_votes(parent_el);
    // could take 3 seconds for block to be accepted
    setTimeout(update_votes, 3000, parent_el);
    $(parent_el).find(".dnVoteThumb").removeClass("fa-spin");
  }).fail(function() {
    M.toast({html: 'Vote failed'});
    update_votes(parent_el);
    $(parent_el).find(".dnVoteThumb").removeClass("fa-spin");
  });
}

function update_votes(e) {
  steem.database.getState("/blockdeals/@" + $(e).data("author") + "/" + $(e).data("permlink")).then(function(d) {
    try {
      post = d['content'][$(e).data("author") + "/" + $(e).data("permlink")];
      if (post.author == $(e).data("author") && post.permlink == $(e).data("permlink")) {
        var up = 0;
        var dn = 0;
        var me = 0;
        var len = post['active_votes'].length;
        for (var i = 0; i < len; i++) {
          if (post['active_votes'][i].voter == username) {
            me = post['active_votes'][i].percent;
          }
          if (post['active_votes'][i].percent > 0) {
            up++;
          }
          else if (post['active_votes'][i].percent < 0) {
            dn++
          }
        }
        $(e).find(".upVote").text(up);
        $(e).find(".dnVote").text(dn);
        $(e).find(".comments").text(post.children);
        var dollhairs = "$"+(parseFloat(post.pending_payout_value.split(" ")[0])+parseFloat(post.total_payout_value.split(" ")[0])).toFixed(2);
        $(e).find(".payout").text(dollhairs);
        if (me > 0) {
          $(e).find(".upVoteThumb").addClass('green-text');
          $(e).find('.supporter').fadeIn();
        } else if (me < 0) {
          $(e).find(".dnVoteThumb").addClass('red-text');
        }
      }
      else {
        console.log("failed to find post: ", $(e).data("author"), $(e).data("permlink"));
        $(e).html("<div class='col s12 center-align'><i class='fas fa-fw fa-exclamation-circle red-text' title='Error reading votes'></i></div>");
      }
    }
    catch(err) {
      console.log(err);
      $(e).html("<i class='fas fa-fw fa-exclamation-circle text-red'></i>");
    }
  }).catch(function(err) {
    console.log("failed to find post: ", $(e).data("author"), $(e).data("permlink"));
    $(e).html("<i class='fas fa-fw fa-exclamation-circle text-red'></i>");
  });
}

function show_comment_form(e) {
  var author = $(e).data("author");
  var permlink = $(e).data("permlink");
  console.log(author, permlink);
  $('#commentform').attr("action", "/comment/" + author + "/" + permlink);
  M.Modal.getInstance(document.getElementById('commentmodal')).open();
}

$(document).ready(function() {
  $('.loginbtn').click(function() {
    window.location.replace(sc2.getLoginURL());
  });
  if (sc2.getLoginURL() != "") {
    $('#loginbtn').prop("disabled", false);
  }
  $('.sidenav').sidenav();
  $('.datepicker').datepicker();
  $('.tooltipped').tooltip();
  $('.collapsible').collapsible();
  $("#country").countrySelect({
    defaultCountry: "",
    preferredCountries: ['au', 'ca', 'gb', 'us']
  });
  $(".dropdown-trigger").dropdown();

  $.get("/countries", function(data) {
    $.each(data, function(index, country_code) {
      $('#country_top').after('<li><a class="truncate" href="/country/' + country_code + '"><div class="country-select"><div class="flag ' + country_code + '"></div></div> ' + countries[country_code] + '</a></li>');
      $('#mobile_freebies').after('<li><a class="truncate" href="/country/' + country_code + '"><div class="country-select"><div class="flag ' + country_code + '"></div></div> ' + countries[country_code] + '</a></li>');
    });
  });

  $.get("/whoami", function(data) {
    username = data['username'];
    $(".lazy").Lazy({
      votes: function(e) {
        update_votes(e);
      }
    });
  });

  $('#image_preview').on("error", function() {
    console.log('image_url appears invalid');
    $('#image_url').addClass("invalid");
  });

  $('#image_url').focusout(function() {
    console.log('image preview loading:', $(this).val());
    var img_url = $(this).val();
    $('#image_preview').attr('src', img_url);
  });

  $('.fixed-action-btn').floatingActionButton();

  $('.modal').modal();

  if (location.hash) {
    if (location.hash === "#country_tip") {
      $('#tips').collapsible('open', 4);
      $('#country_tip').addClass("green lighten-4");
    }
  }
});
