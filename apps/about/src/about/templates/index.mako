## Licensed to Cloudera, Inc. under one
## or more contributor license agreements.  See the NOTICE file
## distributed with this work for additional information
## regarding copyright ownership.  Cloudera, Inc. licenses this file
## to you under the Apache License, Version 2.0 (the
## "License"); you may not use this file except in compliance
## with the License.  You may obtain a copy of the License at
##
##     http://www.apache.org/licenses/LICENSE-2.0
##
## Unless required by applicable law or agreed to in writing, software
## distributed under the License is distributed on an "AS IS" BASIS,
## WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
## See the License for the specific language governing permissions and
## limitations under the License.
<%!
from desktop.views import commonheader, commonfooter
from django.utils.translation import ugettext as _
%>

${ commonheader(_('About Hue'), "about", user, "100px") | n,unicode }

  % if user.is_superuser:
    <div class="row-fluid">
        <div class="subnav subnav-fixed">
          <div class="container-fluid">
            <ul class="nav nav-pills">
              <li class="active"><a href="${url("desktop.views.dump_config")}">${_('Quick start')}</a></li>
              <li><a href="${url("desktop.views.dump_config")}">${_('Configuration')}</a></li>
              <li><a href="${url("desktop.views.log_view")}">${_('Server Logs')}</a></li>
            </ul>
          </div>
        </div>
    </div>
  % endif

<div class="container-fluid">
  <div class="row-fluid">
    <h2>Hue ${version} <img src="/static/art/hue-login-logo.png" /></h2>
    <br/>
    ${ _('Configure Hue through this wizard.') }
  </div>

  <br/>
  <br/>

  <div class="row-fluid">  
<div id="properties" class="section">
        <ul class="nav nav-pills">
          <li class="active"><a href="#step1" class="step">${ _('Step 1: Check Configuration') }</a></li>
          <li><a href="#step2" class="step">${ _('Step 2: Examples') }</a></li>
          <li><a href="#step3" class="step">${ _('Step 3: Users') }</a></li>
          <li><a href="#step4" class="step">${ _('Step 4: Use Hue') }</a></li>
        </ul>

        <div class="steps" >
          <div id="step1" class="stepDetails">
           ${ check_config.content | n,unicode }
        </div>

        <div id="step2" class="stepDetails hide">
        ${ apps_list }
        ## install_examples
Beeswax, Oozie, Jobsub...
        </div>

        <div id="step3" class="stepDetails hide">
         ${ _('Go create or import user in the') } <a href="${ url('useradmin.views.list_users') }">${ _('User Admin') } <img src="/useradmin/static/art/icon_useradmin_24.png"></a> ${ _('application') }.
        </div>

        <div id="step4" class="stepDetails hide">
         ${ _('Start from your home dashboard') }
        </div>

      </div>

        <div class="form-actions">
          <a id="backBtn" class="btn disabled">${ _('Back') }</a>
          <a id="nextBtn" class="btn btn-primary disable-feedback">${ _('Next') }</a>
        </div>  
  </div>  
</div>

<style type="text/css">
  .steps {
    min-height: 400px;
    padding-top: 20px;
  }

  input[type=submit] {
    margin-left: 50px;
  }
</style>

<script src="/static/ext/js/routie-0.3.0.min.js" type="text/javascript" charset="utf-8"></script>

<script type="text/javascript" charset="utf-8">
$(document).ready(function(){
 var currentStep = "step1";

 routie({
    "step1":function () {
      showStep("step1");
    },
    "step2":function () {
      showStep("step2");
    },
    "step3":function () {
      showStep("step3");
    },
    "step4":function () {
      showStep("step4");
    }
  });

  function showStep(step) {
    currentStep = step;
    if (step != "step1") {
      $("#backBtn").removeClass("disabled");
    } else {
      $("#backBtn").addClass("disabled");
    }

    if (step != $(".stepDetails:last").attr("id")) {
      $("#nextBtn").removeClass("disabled");
    } else {
      $("#nextBtn").addClass("disabled");
    }

    $("a.step").parent().removeClass("active");
    $("a.step[href=#" + step + "]").parent().addClass("active");
    $(".stepDetails").hide();
    $("#" + step).show();
  }

  $("#backBtn").click(function () {
    var nextStep = (currentStep.substr(4) * 1 - 1);
    if (nextStep >= 1) {
      routie("step" + nextStep);
    }
  });

  $("#nextBtn").click(function () {
    var nextStep = (currentStep.substr(4) * 1 + 1);
    if (nextStep <= $(".step").length) {
      routie("step" + nextStep);
    }
  });

});
</script>

${ commonfooter(messages) | n,unicode }
